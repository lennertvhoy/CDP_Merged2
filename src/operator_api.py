"""Standalone operator-shell bridge API.

This sidecar keeps the deprecated legacy Chainlit runtime backend intact while
exposing a thin, repo-owned HTTP surface for the operator-shell frontend.
"""

# ruff: noqa: E402

from __future__ import annotations

import json
import time
from pathlib import Path

from src.core.runtime_env import bootstrap_runtime_environment

bootstrap_runtime_environment()

from chainlit.auth import clear_auth_cookie, create_jwt, set_auth_cookie
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.services.operator_auth import (
    authenticate_password_user,
    extract_request_user_context,
    operator_auth_enabled,
    password_auth_enabled,
)
from src.services.operator_bridge import (
    build_operator_bootstrap,
    build_operator_health,
    create_segment_from_filters,
    export_segment,
    get_company_detail,
    get_segment_detail,
    get_thread_detail,
    list_companies,
    list_segments,
    list_threads_for_user,
    resolve_export_file,
)
from src.services.operator_feedback import FeedbackSubmission, submit_operator_feedback

app = FastAPI(
    title="CDP_Merged Operator Bridge",
    version="0.1.0",
    description=(
        "Isolated operator-shell bridge over the existing PostgreSQL-backed CDP runtime. "
        "The operator shell on localhost:3000 is the only future UI; the direct "
        "Chainlit browser surface is deprecated."
    ),
)

LOGIN_RATE_LIMIT_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300
_LOGIN_ATTEMPT_STORE: dict[str, list[float]] = {}


def _login_rate_limit_key(request: Request, username: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    normalized_username = username.strip().lower() or "shared-preview"
    return f"{client_host}:{normalized_username}"


def _prune_login_attempts(key: str, now: float | None = None) -> list[float]:
    current = time.monotonic() if now is None else now
    attempts = [
        timestamp
        for timestamp in _LOGIN_ATTEMPT_STORE.get(key, [])
        if current - timestamp < LOGIN_RATE_LIMIT_WINDOW_SECONDS
    ]
    if attempts:
        _LOGIN_ATTEMPT_STORE[key] = attempts
    else:
        _LOGIN_ATTEMPT_STORE.pop(key, None)
    return attempts


def _login_rate_limited(key: str, now: float | None = None) -> bool:
    return len(_prune_login_attempts(key, now=now)) >= LOGIN_RATE_LIMIT_ATTEMPTS


def _record_login_failure(key: str, now: float | None = None) -> None:
    attempts = _prune_login_attempts(key, now=now)
    current = time.monotonic() if now is None else now
    attempts.append(current)
    _LOGIN_ATTEMPT_STORE[key] = attempts


def _clear_login_failures(key: str) -> None:
    _LOGIN_ATTEMPT_STORE.pop(key, None)


class SegmentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    condition: str | None = None
    keywords: str | None = None
    enterprise_number: str | None = None
    nace_codes: list[str] | None = None
    juridical_codes: list[str] | None = None
    city: str | None = None
    zip_code: str | None = None
    status: str | None = None
    min_start_date: str | None = None
    has_phone: bool | None = None
    has_email: bool | None = None
    email_domain: str | None = None


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "operator-bridge",
        "status": "ok",
        "detail": "Use /api/operator/* for the operator-shell bridge.",
    }


@app.get("/healthz")
async def healthz() -> dict:
    return await build_operator_health()


@app.get("/api/operator/health")
async def operator_health() -> dict:
    return await build_operator_health()


@app.get("/api/operator/bootstrap")
async def operator_bootstrap(request: Request) -> dict:
    return await build_operator_bootstrap(user_context=extract_request_user_context(request))


@app.post("/api/operator/auth/login")
async def operator_auth_login(
    request: Request,
    response: Response,
    username: str = Form(""),
    password: str = Form(...),
) -> dict:
    if not password_auth_enabled():
        raise HTTPException(
            status_code=400,
            detail="Password authentication is not enabled for the operator shell.",
        )

    rate_limit_key = _login_rate_limit_key(request, username)
    if _login_rate_limited(rate_limit_key):
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts. Please wait a few minutes and try again.",
        )

    user = await authenticate_password_user(username, password)
    if user is None:
        _record_login_failure(rate_limit_key)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    _clear_login_failures(rate_limit_key)
    access_token = create_jwt(user)
    set_auth_cookie(request, response, access_token)
    return {
        "status": "ok",
        "user": {
            "identifier": user.identifier,
            "display_name": user.display_name,
        },
    }


@app.post("/api/operator/auth/logout")
async def operator_auth_logout(request: Request, response: Response) -> dict:
    clear_auth_cookie(request, response)
    return {"status": "ok"}


@app.post("/api/operator/feedback")
async def operator_feedback_submit(
    request: Request,
    feedback_text: str = Form(...),
    surface: str = Form(...),
    page_path: str | None = Form(default=None),
    page_url: str | None = Form(default=None),
    thread_id: str | None = Form(default=None),
    company_ref: str | None = Form(default=None),
    segment_ref: str | None = Form(default=None),
    context_json: str = Form(default="{}"),
    screenshots: list[UploadFile] = File(default_factory=list),
) -> dict:
    user_context = extract_request_user_context(request)
    if operator_auth_enabled() and user_context is None:
        raise HTTPException(status_code=401, detail="Authentication required to submit feedback")

    try:
        parsed_context = json.loads(context_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid feedback context JSON.") from exc

    if not isinstance(parsed_context, dict):
        raise HTTPException(status_code=400, detail="Feedback context must be a JSON object.")

    parsed_context.setdefault("request", {})
    parsed_context["request"]["user_agent"] = request.headers.get("user-agent")

    try:
        result = await submit_operator_feedback(
            submission=FeedbackSubmission(
                surface=surface,
                feedback_text=feedback_text,
                page_path=page_path,
                page_url=page_url,
                thread_id=thread_id,
                company_ref=company_ref,
                segment_ref=segment_ref,
                context=parsed_context,
                user_identifier=user_context.get("identifier") if user_context else None,
                user_display_name=user_context.get("display_name") if user_context else None,
            ),
            screenshots=screenshots,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result.model_dump()


@app.get("/api/operator/threads")
async def operator_threads(
    request: Request,
    search: str | None = None,
    limit: int = 25,
) -> dict:
    user_context = extract_request_user_context(request)
    return await list_threads_for_user(
        user_context=user_context,
        search=search,
        limit=limit,
    )


@app.get("/api/operator/threads/{thread_id}")
async def operator_thread_detail(
    thread_id: str,
    request: Request,
) -> dict:
    user_context = extract_request_user_context(request)
    if operator_auth_enabled() and user_context is None:
        raise HTTPException(
            status_code=401, detail="Authentication required to access thread detail"
        )
    payload = await get_thread_detail(thread_id, user_context=user_context)
    if payload is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    # Check ownership if user context exists and thread has an owner
    if user_context and payload.get("thread", {}).get("user_identifier"):
        if payload["thread"]["user_identifier"] != user_context.get("identifier"):
            raise HTTPException(status_code=403, detail="Access denied to this thread")
    return payload


@app.get("/api/operator/companies")
async def operator_companies(
    q: str | None = None,
    city: str | None = None,
    status: str | None = None,
    limit: int = 25,
) -> dict:
    return await list_companies(query=q, city=city, status=status, limit=limit)


@app.get("/api/operator/companies/{company_ref}")
async def operator_company_detail(company_ref: str) -> dict:
    payload = await get_company_detail(company_ref)
    if payload is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return payload


@app.get("/api/operator/segments")
async def operator_segments(search: str | None = None, limit: int = 25) -> dict:
    return await list_segments(search=search, limit=limit)


@app.get("/api/operator/segments/{segment_ref}")
async def operator_segment_detail(segment_ref: str, limit: int = 50) -> dict:
    payload = await get_segment_detail(segment_ref, limit=limit)
    if payload is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    return payload


@app.post("/api/operator/segments")
async def operator_create_segment(payload: SegmentCreateRequest) -> dict:
    return await create_segment_from_filters(payload.model_dump())


@app.post("/api/operator/segments/{segment_ref}/export")
async def operator_export_segment(segment_ref: str) -> dict:
    result = await export_segment(segment_ref)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result


@app.get("/api/operator/downloads/{filename}")
async def operator_download(filename: str):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    try:
        file_path = resolve_export_file(filename)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Export path is not a file")

    media_type = (
        "text/csv" if Path(filename).suffix.lower() == ".csv" else "application/octet-stream"
    )
    return FileResponse(path=file_path, media_type=media_type, filename=filename)
