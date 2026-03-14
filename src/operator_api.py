"""Standalone operator-shell bridge API.

This sidecar exposes a repo-owned HTTP surface for the operator-shell frontend,
replacing the deprecated Chainlit runtime backend for chat streaming.
"""

# ruff: noqa: E402

from __future__ import annotations

import aiosqlite
import json
from datetime import datetime
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from src.core.runtime_env import bootstrap_runtime_environment

bootstrap_runtime_environment()

from chainlit.auth import clear_auth_cookie, create_jwt, set_auth_cookie
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, Field

from src.graph.workflow import compile_workflow

from src.services.local_account_auth import (
    LocalAccountStore,
    LocalAccountExistsError,
    LocalAccountNotFoundError,
    PASSWORD_MIN_LENGTH,
)
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


class ChatTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    thread_id: str | None = None
    chat_profile: str | None = None


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


# ─── Chat Streaming ─────────────────────────────────────────────────────────

# In-memory store for checkpointer connections (per-thread lifecycle)
_checkpointer_pools: dict[str, AsyncSqliteSaver] = {}


def _format_sse_event(data: dict[str, Any]) -> str:
    """Format a dict as an SSE-style JSON line event."""
    return json.dumps(data, default=str) + "\n"


def _sanitize_assistant_content(content: str) -> str:
    """Post-process assistant content to remove internal thinking and tool leakage.
    
    Fixes response quality issues:
    - Removes numbered thinking steps ("1. I need to...", "2. I will...")
    - Hides tool names ("search_profiles", "create_segment", etc.)
    - Removes raw parameter dumps
    """
    import re
    
    # Pattern 1: Remove numbered thinking lines ("1. I need to...", "2. I will...")
    # These are agent reasoning steps that should not be visible
    lines = content.split('\n')
    filtered_lines = []
    for line in lines:
        # Skip lines that look like numbered thinking steps
        if re.match(r'^\d+\.', line.strip()):
            # Check if it's a thinking step (contains reasoning language)
            thinking_patterns = [
                'i need to', 'i will', 'i should', 'let me', 
                'search_', 'create_', 'use ', 'with parameters',
                "i'll", 'first,', 'next,', 'then,',
            ]
            line_lower = line.lower()
            if any(p in line_lower for p in thinking_patterns):
                continue  # Skip this line
        filtered_lines.append(line)
    
    content = '\n'.join(filtered_lines)
    
    # Pattern 2: Replace tool function names with user-friendly descriptions
    tool_replacements = {
        'search_profiles': 'searching',
        'create_segment': 'creating segment',
        'export_segment': 'exporting',
        'push_to_resend': 'sending to Resend',
        'get_company_360': 'retrieving company profile',
    }
    for tool_name, friendly in tool_replacements.items():
        content = content.replace(f"use {tool_name}", f"{friendly}")
        content = content.replace(f"I will {tool_name}", f"I will be {friendly}")
    
    # Pattern 3: Clean up excessive parameter dumps
    # Replace "parameters: keywords='X', city='Y'" with cleaner format
    content = re.sub(r"with parameters:?", "using", content, flags=re.IGNORECASE)
    
    # Pattern 4: Remove parameter key=value noise but keep values
    content = re.sub(r"\w+='([^']+)'", r"'\1'", content)
    
    # Pattern 5: Clean up multiple blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content.strip()


async def _chat_stream_generator(
    request: ChatTurnRequest,
    user_context: dict[str, Any] | None,
) -> AsyncGenerator[str, None]:
    """Generate streaming chat events for the operator shell frontend.
    
    Yields newline-delimited JSON events matching ChatStreamEvent type:
    - thread: Initial thread metadata
    - assistant_delta: Streaming text chunks
    - assistant_message: Final complete message
    - error: Error information
    """
    # Generate or use provided thread_id
    thread_id = request.thread_id or str(uuid.uuid4())
    chat_profile = request.chat_profile or "default"
    
    # Yield thread event first
    yield _format_sse_event({
        "type": "thread",
        "thread_id": thread_id,
        "chat_profile": chat_profile,
        "profile_id": None,
    })
    
    # Initialize checkpointer for this thread if not exists
    checkpointer_path = Path("./data/checkpoints/checkpoints.db")
    checkpointer_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        conn = await aiosqlite.connect(checkpointer_path)
        checkpointer = AsyncSqliteSaver(conn)
        workflow = compile_workflow(checkpointer=checkpointer)
        
        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "language": "",
            "profile_id": None,
        }
        config = {"configurable": {"thread_id": thread_id}}
        
        tool_calls: list[str] = []
        accumulated_content = ""
        message_id = str(uuid.uuid4())
        
        async for event in workflow.astream_events(inputs, config=config, version="v2"):
            kind = event.get("event", "")
            name = event.get("name", "")
            
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk", {})
                if hasattr(chunk, "content") and isinstance(chunk.content, str):
                    delta = chunk.content
                    accumulated_content += delta
                    yield _format_sse_event({
                        "type": "assistant_delta",
                        "thread_id": thread_id,
                        "delta": delta,
                    })
            elif kind == "on_tool_start":
                if name and name != "agent":
                    tool_calls.append(name)
        
        # Sanitize the final content to remove internal thinking and tool leakage
        sanitized_content = _sanitize_assistant_content(accumulated_content)
        
        # Yield final assistant message with cleaned content
        yield _format_sse_event({
            "type": "assistant_message",
            "thread_id": thread_id,
            "tool_calls": tool_calls,
            "suggested_actions": [],  # Could be populated based on context
            "message": {
                "id": message_id,
                "role": "assistant",
                "content": sanitized_content,
                "created_at": datetime.now().isoformat(),
                "status": "complete",
            },
        })
        
    except Exception as exc:
        yield _format_sse_event({
            "type": "error",
            "thread_id": thread_id,
            "error": str(exc),
        })
    finally:
        # Clean up connection
        try:
            await conn.close()
        except Exception:
            pass


@app.post("/api/operator/chat/stream")
async def operator_chat_stream(request: Request, payload: ChatTurnRequest) -> StreamingResponse:
    """Stream chat responses using LangGraph workflow.
    
    Returns newline-delimited JSON events for real-time chat streaming.
    Replaces the deprecated Chainlit WebSocket-based chat interface.
    """
    user_context = extract_request_user_context(request)
    
    if operator_auth_enabled() and user_context is None:
        # Return an error stream for auth failures
        async def auth_error_stream() -> AsyncGenerator[str, None]:
            yield _format_sse_event({
                "type": "error",
                "thread_id": payload.thread_id or str(uuid.uuid4()),
                "error": "Authentication required to start a chat",
            })
        
        return StreamingResponse(
            auth_error_stream(),
            media_type="application/x-ndjson",
            status_code=401,
        )
    
    return StreamingResponse(
        _chat_stream_generator(payload, user_context),
        media_type="application/x-ndjson",
    )


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



def _is_admin_user(user_context: dict[str, Any] | None) -> bool:
    """Check if the current user has admin privileges."""
    if user_context is None:
        return False
    metadata = user_context.get("metadata", {})
    return bool(metadata.get("is_admin", False))


@app.get("/api/operator/admin/users")
async def operator_admin_list_users(request: Request) -> dict:
    """List all local accounts (admin only)."""
    user_context = extract_request_user_context(request)
    
    if operator_auth_enabled() and user_context is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not _is_admin_user(user_context):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    store = LocalAccountStore()
    try:
        accounts = await store.list_accounts(include_inactive=True)
        return {
            "status": "ok",
            "users": [
                {
                    "account_id": acc.account_id,
                    "identifier": acc.identifier,
                    "display_name": acc.display_name,
                    "is_admin": acc.is_admin,
                    "is_active": acc.is_active,
                    "created_at": acc.created_at.isoformat() if acc.created_at else None,
                    "last_login_at": acc.last_login_at.isoformat() if acc.last_login_at else None,
                }
                for acc in accounts
            ],
            "total": len(accounts),
        }
    finally:
        await store.close()


@app.get("/api/operator/admin/me")
async def operator_admin_me(request: Request) -> dict:
    """Get current user's admin status."""
    user_context = extract_request_user_context(request)
    
    if operator_auth_enabled() and user_context is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return {
        "status": "ok",
        "user": {
            "identifier": user_context.get("identifier") if user_context else None,
            "display_name": user_context.get("display_name") if user_context else None,
            "is_admin": _is_admin_user(user_context),
        },
    }



# ============================================================================
# Admin User Management Endpoints
# ============================================================================

class CreateUserRequest(BaseModel):
    """Request to create a new local account."""
    identifier: str = Field(min_length=1, max_length=255, description="Email or username")
    display_name: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=12, description=f"Password (min {PASSWORD_MIN_LENGTH} characters)")
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)


class UpdateUserRequest(BaseModel):
    """Request to update an existing local account."""
    display_name: str | None = Field(default=None, max_length=255)
    is_admin: bool | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class ResetPasswordRequest(BaseModel):
    """Request to reset a user's password."""
    new_password: str = Field(min_length=12, description=f"New password (min {PASSWORD_MIN_LENGTH} characters)")


@app.post("/api/operator/admin/users")
async def operator_admin_create_user(request: Request, payload: CreateUserRequest) -> dict:
    """Create a new local account (admin only)."""
    user_context = extract_request_user_context(request)
    
    if operator_auth_enabled() and user_context is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not _is_admin_user(user_context):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    store = LocalAccountStore()
    try:
        account = await store.create_account(
            identifier=payload.identifier,
            password=payload.password,
            display_name=payload.display_name,
            is_admin=payload.is_admin,
            is_active=payload.is_active,
        )
        return {
            "status": "ok",
            "message": f"User '{account.identifier}' created successfully",
            "user": {
                "account_id": account.account_id,
                "identifier": account.identifier,
                "display_name": account.display_name,
                "is_admin": account.is_admin,
                "is_active": account.is_active,
                "created_at": account.created_at.isoformat() if account.created_at else None,
            },
        }
    except LocalAccountExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await store.close()


@app.patch("/api/operator/admin/users/{identifier:path}")
async def operator_admin_update_user(
    request: Request,
    identifier: str,
    payload: UpdateUserRequest,
) -> dict:
    """Update a local account (admin only)."""
    user_context = extract_request_user_context(request)
    
    if operator_auth_enabled() and user_context is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not _is_admin_user(user_context):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    current_identifier = user_context.get("identifier") if user_context else None
    normalized_target = identifier.strip().lower()
    is_self = current_identifier and current_identifier.lower() == normalized_target
    
    store = LocalAccountStore()
    try:
        # Check if user exists
        account = await store.get_account(identifier, include_inactive=True)
        if account is None:
            raise HTTPException(status_code=404, detail=f"User '{identifier}' not found")
        
        # Prevent self-deactivation
        if is_self and payload.is_active is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
        
        # Prevent self-demotion from admin (would lock out admin access)
        if is_self and payload.is_admin is False and account.is_admin:
            raise HTTPException(status_code=400, detail="Cannot remove your own admin privileges")
        
        # Safety check: prevent removing the last admin
        if payload.is_admin is False and account.is_admin:
            admin_count = await store.count_admin_accounts()
            if admin_count <= 1:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot remove the last admin account. Create another admin first."
                )
        
        # Apply updates
        if payload.is_active is not None:
            account = await store.set_account_active(identifier, is_active=payload.is_active)
        
        if payload.display_name is not None:
            account = await store.set_display_name(identifier, display_name=payload.display_name)
        
        if payload.is_admin is not None:
            account = await store.set_admin(identifier, is_admin=payload.is_admin)
        
        return {
            "status": "ok",
            "message": f"User '{identifier}' updated successfully",
            "user": {
                "account_id": account.account_id,
                "identifier": account.identifier,
                "display_name": account.display_name,
                "is_admin": account.is_admin,
                "is_active": account.is_active,
                "updated_at": account.updated_at.isoformat() if account.updated_at else None,
            },
        }
    except LocalAccountNotFoundError:
        raise HTTPException(status_code=404, detail=f"User '{identifier}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await store.close()


@app.post("/api/operator/admin/users/{identifier:path}/reset-password")
async def operator_admin_reset_password(
    request: Request,
    identifier: str,
    payload: ResetPasswordRequest,
) -> dict:
    """Reset a user's password (admin only)."""
    user_context = extract_request_user_context(request)
    
    if operator_auth_enabled() and user_context is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not _is_admin_user(user_context):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    store = LocalAccountStore()
    try:
        account = await store.update_password(identifier, payload.new_password)
        return {
            "status": "ok",
            "message": f"Password reset successfully for '{identifier}'",
            "user": {
                "account_id": account.account_id,
                "identifier": account.identifier,
                "display_name": account.display_name,
                "is_admin": account.is_admin,
                "is_active": account.is_active,
                "updated_at": account.updated_at.isoformat() if account.updated_at else None,
            },
        }
    except LocalAccountNotFoundError:
        raise HTTPException(status_code=404, detail=f"User '{identifier}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await store.close()


@app.delete("/api/operator/admin/users/{identifier:path}")
async def operator_admin_delete_user(
    request: Request,
    identifier: str,
) -> dict:
    """Permanently delete a local account (admin only).
    
    Protections:
    - Cannot delete your own account (would break current session)
    - Cannot delete the last remaining admin (would lock out admin access)
    """
    user_context = extract_request_user_context(request)
    
    if operator_auth_enabled() and user_context is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not _is_admin_user(user_context):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    current_identifier = user_context.get("identifier") if user_context else None
    normalized_target = identifier.strip().lower()
    
    # Prevent self-deletion
    if current_identifier and current_identifier.lower() == normalized_target:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    store = LocalAccountStore()
    try:
        # Get target account to check if it's the last admin
        target_account = await store.get_account(identifier, include_inactive=True)
        if target_account is None:
            raise HTTPException(status_code=404, detail=f"User '{identifier}' not found")
        
        # Prevent deleting the last admin
        if target_account.is_admin:
            admin_count = await store.count_admin_accounts()
            if admin_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete the last admin account. Create another admin first."
                )
        
        # Perform deletion
        await store.delete_account(identifier)
        
        return {
            "status": "ok",
            "message": f"User '{identifier}' permanently deleted",
            "deleted_identifier": identifier,
        }
    except LocalAccountNotFoundError:
        raise HTTPException(status_code=404, detail=f"User '{identifier}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await store.close()
