"""Thin PostgreSQL-backed bridge for the operator-shell sidecar."""

from __future__ import annotations

import json
import re
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.ai_interface.tools.artifact import ARTIFACT_ROOT
from src.ai_interface.tools.export import export_segment_to_csv
from src.core.logger import get_logger
from src.services.canonical_segments import CanonicalSegmentService
from src.services.operator_auth import operator_auth_config, operator_auth_enabled
from src.services.postgresql_search import CompanySearchFilters, get_search_service
from src.services.runtime_support_schema import ensure_runtime_support_schema
from src.services.unified_360_queries import Unified360Service

logger = get_logger(__name__)

# Use the same artifact root as the artifact tool for consistency
EXPORT_ROOT = ARTIFACT_ROOT
DEFAULT_THREAD_LIMIT = 25
DEFAULT_COMPANY_LIMIT = 25
DEFAULT_SEGMENT_LIMIT = 25


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value


def operator_requires_user_scope() -> bool:
    """Mirror the current backend ownership policy without inventing a new one."""
    return operator_auth_enabled()


def _surface_mode(real: bool) -> str:
    return "backend" if real else "mock"


async def _get_pool():
    search_service = get_search_service()
    await search_service.ensure_connected()
    await ensure_runtime_support_schema(search_service._client)
    pool = search_service._client.pool
    assert pool is not None
    return pool


def _linked_systems(row: dict[str, Any]) -> list[str]:
    systems = ["KBO"]
    if row.get("has_teamleader"):
        systems.append("Teamleader")
    if row.get("has_exact"):
        systems.append("Exact")
    if row.get("has_autotask"):
        systems.append("Autotask")
    if row.get("website_url"):
        systems.append("Website")
    return systems


def _normalize_kbo(company_ref: str) -> str | None:
    digits = re.sub(r"\D", "", company_ref)
    return digits if len(digits) == 10 else None


def thread_surface_state(user_context: dict[str, Any] | None = None) -> dict[str, Any]:
    if operator_requires_user_scope():
        return {
            "status": "ok",
            "reason": "user_scoped" if user_context else "authentication_required",
            "message": (
                "Your conversations are only visible after you sign in."
                if not user_context
                else f"Showing conversations for {user_context['identifier']}."
            ),
        }

    return {
        "status": "ok",
        "reason": "anonymous_local_runtime",
        "message": (
            "Chainlit auth is currently disabled, so the operator bridge can read the "
            "existing thread tables without creating a second ownership model."
        ),
    }


async def build_operator_health() -> dict[str, Any]:
    search_service = get_search_service()
    probe = await search_service.readiness_probe()
    return {
        "status": "ok",
        "service": "operator-bridge",
        "backend": {
            "service": "cdp-merged",
            "query_plane": probe["backend"],
            "companies_table": probe["companies_table"],
        },
    }


async def build_operator_bootstrap(user_context: dict[str, Any] | None = None) -> dict[str, Any]:
    auth = operator_auth_config()
    access_gate_active = bool(auth["required"] and user_context is None)

    if access_gate_active:
        uses_local_accounts = auth["password_mode"] == "local-accounts"
        return {
            "status": "ok",
            "phase": "access_gate",
            "health": None,
            "session": {
                "mode": "access_gate",
                "authenticated": False,
                "user": None,
                "auth": auth,
                "detail": "Private preview. Sign in to continue.",
                "gate": {
                    "title": "Private Access",
                    "subtitle": "This preview is temporarily protected while shared online.",
                    "help": (
                        "Use the email and password shared with you to continue."
                        if uses_local_accounts
                        else "Enter the access password to continue."
                    ),
                },
            },
            "surfaces": None,
        }

    health = await build_operator_health()
    threads = thread_surface_state(user_context)

    return {
        "status": "ok",
        "phase": "app",
        "health": health["backend"],
        "session": {
            "mode": "user_scoped" if operator_requires_user_scope() else "anonymous_local",
            "authenticated": bool(user_context),
            "user": (
                {
                    "identifier": user_context["identifier"],
                    "display_name": user_context.get("display_name"),
                    "is_admin": user_context.get("metadata", {}).get("is_admin", False),
                }
                if user_context
                else None
            ),
            "auth": auth,
            "detail": (
                f"Signed in as {user_context.get('display_name') or user_context['identifier']}."
                if user_context
                else threads["message"]
            ),
            "gate": None,
        },
        "surfaces": {
            "chat": {
                "mode": "backend",
                "status": "ok",
                "detail": "Chat is ready.",
            },
            "threads": {
                "mode": _surface_mode(threads["status"] == "ok"),
                "status": threads["status"],
                "detail": threads["message"],
            },
            "companies": {
                "mode": "backend",
                "status": "ok",
                "detail": "Browse company records and open the detail panel.",
            },
            "segments": {
                "mode": "backend",
                "status": "ok",
                "detail": "Create, review, and export saved segments.",
            },
            "sources": {
                "mode": "mock",
                "status": "mocked",
                "detail": "Not available in this preview.",
            },
            "pipelines": {
                "mode": "mock",
                "status": "mocked",
                "detail": "Not available in this preview.",
            },
            "activity": {
                "mode": "mock",
                "status": "mocked",
                "detail": "Not available in this preview.",
            },
            "settings": {
                "mode": "mock",
                "status": "mocked",
                "detail": "Not available in this preview.",
            },
        },
    }


async def list_threads(
    *, search: str | None = None, limit: int = DEFAULT_THREAD_LIMIT
) -> dict[str, Any]:
    """List threads (anonymous mode only)."""
    surface_state = thread_surface_state()
    if surface_state["status"] != "ok":
        return {
            "status": "unavailable",
            "threads": [],
            "surface": surface_state,
        }

    # When auth is required, use list_threads_for_user instead
    if operator_requires_user_scope():
        return {
            "status": "unavailable",
            "threads": [],
            "surface": {
                "status": "unavailable",
                "reason": "user_scoped_thread_bridge_not_connected",
                "message": (
                    "Thread listing requires authentication. "
                    "Use list_threads_for_user with user_context."
                ),
            },
        }

    return await _list_threads_query(search=search, limit=limit, user_identifier=None)


async def list_threads_for_user(
    *,
    user_context: dict[str, Any] | None,
    search: str | None = None,
    limit: int = DEFAULT_THREAD_LIMIT,
) -> dict[str, Any]:
    """List threads for a specific user (user-scoped mode).

    When user_context is provided, only returns threads owned by that user.
    When user_context is None and auth is disabled, returns all threads.
    """
    surface_state = thread_surface_state(user_context)
    if surface_state["status"] != "ok":
        return {
            "status": "unavailable",
            "threads": [],
            "surface": surface_state,
        }

    # If auth is required but no user context provided, return empty
    if operator_requires_user_scope() and not user_context:
        return {
            "status": "ok",
            "threads": [],
            "surface": {
                "status": "ok",
                "reason": "authentication_required",
                "message": "Sign in to view your conversations.",
            },
        }

    user_identifier = user_context.get("identifier") if user_context else None
    return await _list_threads_query(search=search, limit=limit, user_identifier=user_identifier)


async def _list_threads_query(
    *,
    search: str | None,
    limit: int,
    user_identifier: str | None,
) -> dict[str, Any]:
    """Internal query to list threads with optional user filtering."""
    pool = await _get_pool()
    bounded_limit = max(1, min(limit, 100))
    params: list[Any] = [bounded_limit]
    clauses = ["1=1"]

    # Filter by user if provided (user-scoped mode)
    if user_identifier:
        params.append(user_identifier)
        clauses.append(f"u.identifier = ${len(params)}")

    if search:
        params.append(f"%{search.strip()}%")
        clauses.append(f"COALESCE(t.name, '') ILIKE ${len(params)}")

    query = f"""
        SELECT
            t.thread_id::text AS thread_id,
            COALESCE(NULLIF(t.name, ''), 'New conversation') AS title,
            t.created_at,
            t.updated_at,
            u.identifier AS user_identifier,
            ts.last_search_tql,
            ts.last_tool_artifacts,
            COALESCE(step_summary.total_steps, 0) AS total_steps,
            COALESCE(step_summary.user_messages, 0) AS user_messages,
            last_step.preview AS last_preview
        FROM app_chat_threads t
        LEFT JOIN app_chat_users u ON u.user_id = t.user_id
        LEFT JOIN app_chat_thread_state ts ON ts.thread_id = t.thread_id
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) AS total_steps,
                COUNT(*) FILTER (
                    WHERE COALESCE(step_json->>'input', '') <> ''
                ) AS user_messages
            FROM app_chat_steps s
            WHERE s.thread_id = t.thread_id
        ) AS step_summary ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                COALESCE(
                    NULLIF(s.step_json->>'output', ''),
                    NULLIF(s.step_json->>'input', ''),
                    NULLIF(s.step_json->>'name', '')
                ) AS preview
            FROM app_chat_steps s
            WHERE s.thread_id = t.thread_id
            ORDER BY s.created_at DESC
            LIMIT 1
        ) AS last_step ON TRUE
        WHERE {" AND ".join(clauses)}
        ORDER BY t.updated_at DESC
        LIMIT $1
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    threads = [
        {
            "id": row["thread_id"],
            "title": row["title"],
            "updated_at": _json_ready(row["updated_at"]),
            "created_at": _json_ready(row["created_at"]),
            "user_identifier": row["user_identifier"],
            "total_steps": int(row["total_steps"] or 0),
            "user_messages": int(row["user_messages"] or 0),
            "preview": row["last_preview"],
            "resume_context": {
                "last_search_tql": row["last_search_tql"],
                "last_tool_artifacts": _json_ready(row["last_tool_artifacts"] or {}),
            },
        }
        for row in rows
    ]

    surface = {
        "status": "ok",
        "reason": "user_scoped" if user_identifier else "anonymous",
        "message": (
            f"Showing conversations for {user_identifier}."
            if user_identifier
            else "Showing available conversations."
        ),
    }

    return {
        "status": "ok",
        "threads": threads,
        "surface": surface,
    }


async def get_thread_detail(
    thread_id: str, user_context: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    surface_state = thread_surface_state(user_context)
    if surface_state["status"] != "ok":
        return {
            "status": "unavailable",
            "thread": None,
            "surface": surface_state,
        }

    if operator_requires_user_scope() and not user_context:
        return {
            "status": "ok",
            "thread": None,
            "surface": {
                "status": "ok",
                "reason": "authentication_required",
                "message": "Sign in to view this conversation.",
            },
        }

    pool = await _get_pool()

    async with pool.acquire() as conn:
        thread_row = await conn.fetchrow(
            """
            SELECT
                t.thread_id::text AS thread_id,
                COALESCE(NULLIF(t.name, ''), 'New conversation') AS title,
                t.metadata,
                t.created_at,
                t.updated_at,
                u.identifier AS user_identifier,
                ts.last_search_tql,
                ts.last_search_params,
                ts.last_tool_artifacts
            FROM app_chat_threads t
            LEFT JOIN app_chat_users u ON u.user_id = t.user_id
            LEFT JOIN app_chat_thread_state ts ON ts.thread_id = t.thread_id
            WHERE t.thread_id = $1
            """,
            thread_id,
        )
        if thread_row is None:
            return None

        step_rows = await conn.fetch(
            """
            SELECT
                step_id::text AS step_id,
                parent_step_id::text AS parent_step_id,
                step_json,
                created_at
            FROM app_chat_steps
            WHERE thread_id = $1
            ORDER BY created_at ASC
            """,
            thread_id,
        )

    steps = []
    for row in step_rows:
        payload = row["step_json"] or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        steps.append(
            {
                "id": row["step_id"],
                "parent_id": row["parent_step_id"],
                "name": payload.get("name"),
                "type": payload.get("type"),
                "input": payload.get("input"),
                "output": payload.get("output"),
                "is_error": payload.get("isError"),
                "metadata": _json_ready(payload.get("metadata") or {}),
                "created_at": _json_ready(row["created_at"]),
            }
        )

    thread_payload = {
        "id": thread_row["thread_id"],
        "title": thread_row["title"],
        "created_at": _json_ready(thread_row["created_at"]),
        "updated_at": _json_ready(thread_row["updated_at"]),
        "user_identifier": thread_row["user_identifier"],
        "metadata": _json_ready(thread_row["metadata"] or {}),
        "resume_context": {
            "last_search_tql": thread_row["last_search_tql"],
            "last_search_params": _json_ready(thread_row["last_search_params"] or {}),
            "last_tool_artifacts": _json_ready(thread_row["last_tool_artifacts"] or {}),
        },
        "steps": steps,
    }

    return {
        "status": "ok",
        "thread": thread_payload,
        "surface": surface_state,
    }


async def list_companies(
    *,
    query: str | None = None,
    city: str | None = None,
    status: str | None = None,
    limit: int = DEFAULT_COMPANY_LIMIT,
) -> dict[str, Any]:
    pool = await _get_pool()
    bounded_limit = max(1, min(limit, 100))
    params: list[Any] = []
    clauses = ["1=1"]

    if query:
        params.append(f"%{query.strip()}%")
        placeholder = f"${len(params)}"
        clauses.append(
            "("
            f"uc360.kbo_company_name ILIKE {placeholder} OR "
            f"COALESCE(uc360.tl_company_name, '') ILIKE {placeholder} OR "
            f"COALESCE(uc360.exact_company_name, '') ILIKE {placeholder} OR "
            f"uc360.kbo_number ILIKE {placeholder}"
            ")"
        )

    if city:
        params.append(f"%{city.strip()}%")
        clauses.append(f"COALESCE(uc360.kbo_city, '') ILIKE ${len(params)}")

    if status:
        params.append(status.strip().upper())
        clauses.append(f"COALESCE(uc360.kbo_status, '') = ${len(params)}")

    where_clause = " AND ".join(clauses)
    count_sql = f"SELECT COUNT(*) FROM unified_company_360 uc360 WHERE {where_clause}"
    list_sql = f"""
        SELECT
            uc360.company_uid,
            uc360.kbo_number,
            uc360.vat_number,
            uc360.kbo_company_name,
            uc360.kbo_status,
            uc360.kbo_city,
            uc360.nace_code,
            uc360.nace_description,
            uc360.website_url,
            uc360.exact_account_manager,
            uc360.autotask_open_tickets,
            uc360.identity_link_status,
            uc360.total_source_count,
            uc360.has_teamleader,
            uc360.has_exact,
            uc360.has_autotask,
            uc360.last_updated_at,
            upr.exact_revenue_ytd,
            upr.exact_outstanding,
            upr.total_exposure
        FROM unified_company_360 uc360
        LEFT JOIN unified_pipeline_revenue upr ON upr.kbo_number = uc360.kbo_number
        WHERE {where_clause}
        ORDER BY upr.total_exposure DESC NULLS LAST, uc360.kbo_company_name ASC
        LIMIT ${len(params) + 1}
    """

    async with pool.acquire() as conn:
        count_row = await conn.fetchrow(count_sql, *params)
        rows = await conn.fetch(list_sql, *params, bounded_limit)

    companies = [
        {
            "id": row["kbo_number"] or row["company_uid"],
            "company_uid": row["company_uid"],
            "kbo_number": row["kbo_number"],
            "vat_number": row["vat_number"],
            "name": row["kbo_company_name"],
            "city": row["kbo_city"],
            "status": row["kbo_status"],
            "industry": row["nace_description"],
            "website_url": row["website_url"],
            "account_manager": row["exact_account_manager"],
            "open_tickets": row["autotask_open_tickets"],
            "exact_revenue_ytd": _json_ready(row["exact_revenue_ytd"]),
            "exact_outstanding": _json_ready(row["exact_outstanding"]),
            "identity_link_status": row["identity_link_status"],
            "linked_systems": _linked_systems(dict(row)),
            "last_updated_at": _json_ready(row["last_updated_at"]),
        }
        for row in rows
    ]

    return {
        "status": "ok",
        "total": int(count_row[0] or 0) if count_row else len(companies),
        "companies": companies,
    }


async def get_company_detail(company_ref: str) -> dict[str, Any] | None:
    pool = await _get_pool()
    normalized_kbo = _normalize_kbo(company_ref)
    unified_service = Unified360Service(pool=pool)

    if normalized_kbo:
        profile = await unified_service.get_company_360_profile(kbo_number=normalized_kbo)
    else:
        profile = await unified_service.get_company_360_profile(company_uid=company_ref)

    if profile is None:
        return None

    activity = (
        await unified_service.get_company_activity_timeline(profile.kbo_number, limit=20)
        if profile.kbo_number
        else []
    )

    return {
        "status": "ok",
        "company": {
            "company_uid": profile.company_uid,
            "kbo_number": profile.kbo_number,
            "vat_number": profile.vat_number,
            "name": profile.kbo_company_name,
            "city": profile.kbo_city,
            "legal_form": profile.legal_form,
            "status": profile.kbo_status,
            "website_url": profile.website_url,
            "employee_count": profile.employee_count,
            "nace_code": profile.nace_code,
            "nace_description": profile.nace_description,
            "identity_link_status": profile.identity_link_status,
            "last_updated_at": _json_ready(profile.last_updated_at),
            "linked_systems": _linked_systems(profile.__dict__),
        },
        "sources": {
            "teamleader": {
                "linked": profile.has_teamleader,
                "company_id": profile.tl_company_id,
                "company_name": profile.tl_company_name,
                "status": profile.tl_status,
                "customer_type": profile.tl_customer_type,
                "email": profile.tl_email,
                "phone": profile.tl_phone,
            },
            "exact": {
                "linked": profile.has_exact,
                "customer_id": profile.exact_customer_id,
                "company_name": profile.exact_company_name,
                "status": profile.exact_status,
                "credit_line": _json_ready(profile.exact_credit_line),
                "payment_terms": profile.exact_payment_terms,
                "account_manager": profile.exact_account_manager,
            },
            "autotask": {
                "linked": profile.has_autotask,
                "company_id": profile.autotask_company_id,
                "company_name": profile.autotask_company_name,
                "company_type": profile.autotask_company_type,
                "phone": profile.autotask_phone,
                "website": profile.autotask_website,
                "total_tickets": profile.autotask_total_tickets,
                "open_tickets": profile.autotask_open_tickets,
                "last_ticket_at": _json_ready(profile.autotask_last_ticket_at),
                "total_contracts": profile.autotask_total_contracts,
                "active_contracts": profile.autotask_active_contracts,
                "total_contract_value": _json_ready(profile.autotask_total_contract_value),
                "last_contract_start": _json_ready(profile.autotask_last_contract_start),
            },
        },
        "pipeline": _json_ready(profile.pipeline.__dict__ if profile.pipeline else {}),
        "financials": _json_ready(profile.financials.__dict__ if profile.financials else {}),
        "activity": _json_ready([record.__dict__ for record in activity]),
    }


async def list_segments(
    *, search: str | None = None, limit: int = DEFAULT_SEGMENT_LIMIT
) -> dict[str, Any]:
    pool = await _get_pool()
    bounded_limit = max(1, min(limit, 100))
    params: list[Any] = []
    clauses = ["sd.is_active = TRUE"]

    if search:
        params.append(f"%{search.strip()}%")
        placeholder = f"${len(params)}"
        clauses.append(
            "("
            f"sd.segment_name ILIKE {placeholder} OR "
            f"COALESCE(sd.description, '') ILIKE {placeholder} OR "
            f"sd.segment_key ILIKE {placeholder}"
            ")"
        )

    query = f"""
        SELECT
            sd.segment_id::text AS segment_id,
            sd.segment_key,
            sd.segment_name,
            sd.description,
            sd.owner,
            sd.updated_at,
            COUNT(sm.uid) AS member_count
        FROM segment_definitions sd
        LEFT JOIN segment_memberships sm ON sm.segment_id = sd.segment_id
        WHERE {" AND ".join(clauses)}
        GROUP BY sd.segment_id, sd.segment_key, sd.segment_name, sd.description, sd.owner, sd.updated_at
        ORDER BY sd.updated_at DESC
        LIMIT ${len(params) + 1}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params, bounded_limit)

    segments = [
        {
            "id": row["segment_id"],
            "segment_key": row["segment_key"],
            "name": row["segment_name"],
            "description": row["description"],
            "owner": row["owner"],
            "member_count": int(row["member_count"] or 0),
            "updated_at": _json_ready(row["updated_at"]),
        }
        for row in rows
    ]

    return {
        "status": "ok",
        "segments": segments,
    }


async def get_segment_detail(segment_ref: str, *, limit: int = 50) -> dict[str, Any] | None:
    canonical_service = CanonicalSegmentService()
    segment = await canonical_service.get_segment_members(segment_ref, limit=limit)
    if segment is None:
        return None

    stats = await canonical_service.get_segment_stats(segment_ref)
    return {
        "status": "ok",
        "segment": _json_ready(segment),
        "stats": _json_ready(stats or {}),
    }


async def create_segment_from_filters(payload: dict[str, Any]) -> dict[str, Any]:
    canonical_service = CanonicalSegmentService()
    filters = CompanySearchFilters(
        keywords=payload.get("keywords"),
        enterprise_number=payload.get("enterprise_number"),
        nace_codes=payload.get("nace_codes"),
        juridical_codes=payload.get("juridical_codes"),
        city=payload.get("city"),
        zip_code=payload.get("zip_code"),
        status=payload.get("status"),
        min_start_date=payload.get("min_start_date"),
        has_phone=payload.get("has_phone"),
        has_email=payload.get("has_email"),
        email_domain=payload.get("email_domain"),
    )
    result = await canonical_service.upsert_segment(
        name=payload["name"],
        description=payload.get("description"),
        filters=filters,
        condition=payload.get("condition"),
        owner="operator-shell",
    )
    return {
        "status": "ok",
        "segment": _json_ready(result),
    }


async def export_segment(segment_ref: str) -> dict[str, Any]:
    raw = await export_segment_to_csv.ainvoke({"segment_id": segment_ref})
    payload = json.loads(raw)
    if payload.get("status") == "ok" and payload.get("filename"):
        payload["download_url"] = f"/operator-api/downloads/{payload['filename']}"
    return _json_ready(payload)


def resolve_export_file(filename: str) -> Path:
    # Support both segment exports and agent artifact downloads
    # Try artifact root first (output/agent_artifacts), fall back to legacy export path
    for root in [ARTIFACT_ROOT, Path(tempfile.gettempdir()) / "cdp_exports"]:
        file_path = (root / filename).resolve()
        if not str(file_path).startswith(str(root.resolve())):
            raise ValueError("access_denied")
        if file_path.exists():
            return file_path
    # Return artifact root path as default (will trigger 404 if not exists)
    file_path = (ARTIFACT_ROOT / filename).resolve()
    if not str(file_path).startswith(str(ARTIFACT_ROOT.resolve())):
        raise ValueError("access_denied")
    return file_path
