"""
Chainlit UI for CDP_Merged.
Merges CDPT's working workflow with CDP's transparent assistant patterns.
"""

import uuid
from pathlib import Path

import aiosqlite
import chainlit as cl
import httpx
from chainlit.oauth_providers import get_configured_oauth_providers
from chainlit.server import app as chainlit_server_app
from chainlit.types import ThreadDict
from chainlit.user import User
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.ai_interface.tools.artifact import ARTIFACT_ROOT
from src.config import settings
from src.core.constants import MAX_QUERY_LENGTH
from src.core.database_url import database_config_source, resolve_database_url
from src.core.exceptions import TracardiError
from src.core.logger import bind_trace_id, clear_trace_id, configure_logging, get_logger
from src.core.metrics import ERRORS_TOTAL, QUERY_REQUESTS_TOTAL
from src.graph.workflow import compile_workflow
from src.services.postgresql_search import get_search_service
from src.services.runtime_support_schema import ensure_runtime_support_schema
from src.services.tracardi import TracardiClient
from src.ui.actions import build_action_reply, build_welcome_actions
from src.ui.components import build_chat_profiles, build_starters
from src.ui.formatters import DEFAULT_CHAT_PROFILE, build_status_cards, build_welcome_markdown

# Configure structured logging on startup
configure_logging(settings.LOG_LEVEL)

logger = get_logger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_ENDPOINT_PATHS = {
    "/healthz",
    "/project/healthz",
    "/readinessz",
    "/project/readinessz",
}

THREAD_TITLE_MAX_LENGTH = 60  # Shorter limit for sidebar readability


def _build_chainlit_data_layer(
    *,
    database_url: str | None = None,
    data_layer_cls=None,
):
    """Use repo-managed chat tables instead of Chainlit's default schema."""
    if not _database_config_source():
        return None

    resolved_database_url = database_url or resolve_database_url(REPO_ROOT)
    layer_cls = data_layer_cls
    if layer_cls is None:
        from src.services.chainlit_data_layer import PostgreSQLChainlitDataLayer

        layer_cls = PostgreSQLChainlitDataLayer

    return layer_cls(database_url=resolved_database_url)


cl.data_layer(_build_chainlit_data_layer)


def _oauth_display_name(raw_user_data: dict[str, str], default_user: User) -> str | None:
    return (
        raw_user_data.get("name")
        or raw_user_data.get("display_name")
        or raw_user_data.get("displayName")
        or raw_user_data.get("given_name")
        or raw_user_data.get("preferred_username")
        or default_user.display_name
    )


def _normalize_dev_auth_identifier(username: str) -> str | None:
    identifier = username.strip()
    return identifier or None


async def password_auth_user_callback(username: str, password: str) -> User | None:
    """Allow local-only password auth for authenticated history verification."""
    identifier = _normalize_dev_auth_identifier(username)
    expected_password = settings.CHAINLIT_DEV_AUTH_PASSWORD

    if not identifier:
        logger.warning("dev_password_auth_rejected", reason="missing_username")
        return None

    if not expected_password or password != expected_password:
        logger.warning(
            "dev_password_auth_rejected", reason="invalid_password", identifier=identifier
        )
        return None

    return User(
        identifier=identifier,
        display_name=identifier,
        metadata={"provider": "dev-password"},
    )


def _register_password_auth_callback() -> bool:
    """Register dev-only password auth only when explicitly enabled."""
    if not settings.CHAINLIT_DEV_AUTH_ENABLED:
        return False

    if not settings.CHAINLIT_DEV_AUTH_PASSWORD:
        logger.warning("dev_password_auth_disabled", reason="missing_password")
        return False

    cl.password_auth_callback(password_auth_user_callback)
    logger.info("dev_password_auth_registered")
    return True


PASSWORD_AUTH_ENABLED = _register_password_auth_callback()


def _validate_azure_ad_domain(email: str) -> bool:
    """Validate that the Azure AD user belongs to an allowed domain."""
    if not settings.AZURE_AD_ALLOWED_DOMAINS:
        return True  # No domain restriction configured

    allowed_domains = [d.strip().lower() for d in settings.AZURE_AD_ALLOWED_DOMAINS.split(",")]
    email_domain = email.split("@")[-1].lower() if "@" in email else ""

    if email_domain not in allowed_domains:
        logger.warning(
            "azure_ad_domain_rejected",
            email_domain=email_domain,
            allowed_domains=allowed_domains,
        )
        return False
    return True


async def oauth_user_callback(
    provider_id: str,
    _token: str,
    raw_user_data: dict[str, str],
    default_user: User,
    _id_token: str | None = None,
) -> User | None:
    """Accept authenticated OAuth users and normalize basic profile fields.

    Args:
        provider_id: OAuth provider identifier (e.g., 'google', 'azure-ad')
        _token: Access token from the provider (unused but required by Chainlit)
        raw_user_data: User profile data from the OAuth provider
        default_user: Default user object from Chainlit with base identifier
        _id_token: Optional ID token (unused but required by Chainlit)

    Returns:
        User: Normalized user with display name and provider metadata,
              or None to reject the authentication.
    """
    if not default_user.identifier:
        logger.warning("oauth_callback_rejected", reason="missing_user_identifier")
        return None

    # Extract email for domain validation (Azure AD specific)
    email = (
        raw_user_data.get("mail")
        or raw_user_data.get("email")
        or raw_user_data.get("userPrincipalName")
        or default_user.identifier
    )

    # Azure AD domain validation
    if provider_id == "azure-ad" and not _validate_azure_ad_domain(email):
        logger.warning(
            "azure_ad_auth_rejected",
            reason="domain_not_allowed",
            identifier=default_user.identifier,
            email=email,
        )
        return None

    metadata = dict(default_user.metadata or {})
    metadata["provider"] = provider_id
    metadata["email"] = email

    # Capture additional Azure AD claims if present
    if provider_id == "azure-ad":
        metadata["tenant_id"] = raw_user_data.get("tid") or settings.AZURE_AD_TENANT_ID
        metadata["oid"] = raw_user_data.get("oid")  # Object ID

    return User(
        identifier=default_user.identifier,
        display_name=_oauth_display_name(raw_user_data, default_user),
        metadata=metadata,
    )


def _register_oauth_callback() -> bool:
    """Register OAuth only when provider env vars exist; bare decorators raise otherwise."""
    try:
        configured_providers = tuple(get_configured_oauth_providers())
    except Exception as exc:
        logger.warning("oauth_provider_detection_failed", error=str(exc))
        return False

    if not configured_providers:
        return False

    cl.oauth_callback(oauth_user_callback)
    logger.info("oauth_callback_registered", providers=list(configured_providers))
    return True


OAUTH_CALLBACK_ENABLED = _register_oauth_callback()


def _safe_user_session_get(key: str, default=None):
    """Read Chainlit session state without failing when no request context exists."""
    try:
        return cl.user_session.get(key, default)
    except Exception:
        return default


def _current_thread_id() -> str | None:
    """Prefer Chainlit's persistent thread id over the websocket session id."""
    try:
        from chainlit.context import context as chainlit_context

        session = getattr(chainlit_context, "session", None)
        thread_id = getattr(session, "thread_id", None)
        if thread_id:
            return str(thread_id)
    except Exception:
        pass

    return _safe_user_session_get("thread_id") or _safe_user_session_get("id")


async def _resolve_profile_id(thread_id: str, profile_id_hint: str | None = None) -> str | None:
    """Keep session bootstrap resilient when Tracardi is unavailable."""
    try:
        tracardi = TracardiClient()
        profile = await tracardi.get_or_create_profile(session_id=thread_id)
        return profile.get("id") if profile else profile_id_hint
    except (TracardiError, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("tracardi_profile_bootstrap_failed", error=str(exc))
        return profile_id_hint


async def _initialize_chat_session(
    *,
    thread_id: str | None = None,
    chat_profile: str | None = None,
    profile_id_hint: str | None = None,
) -> tuple[str, str, str | None]:
    """Prepare the workflow/checkpointer state for both new and resumed chats."""
    trace_id = str(uuid.uuid4())
    bind_trace_id(trace_id)
    cl.user_session.set("trace_id", trace_id)

    checkpointer_path = Path("./data/checkpoints/checkpoints.db")
    checkpointer_path.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(checkpointer_path)
    checkpointer = AsyncSqliteSaver(conn)
    workflow = compile_workflow(checkpointer=checkpointer)
    cl.user_session.set("workflow", workflow)
    cl.user_session.set("checkpointer_conn", conn)

    session_id = _safe_user_session_get("id")
    resolved_thread_id = thread_id or _current_thread_id() or session_id or str(uuid.uuid4())
    cl.user_session.set("thread_id", resolved_thread_id)

    resolved_chat_profile = (
        chat_profile or cl.user_session.get("chat_profile") or DEFAULT_CHAT_PROFILE
    )
    cl.user_session.set("chat_profile", resolved_chat_profile)

    profile_id = await _resolve_profile_id(resolved_thread_id, profile_id_hint)
    cl.user_session.set("profile_id", profile_id)

    return resolved_thread_id, resolved_chat_profile, profile_id


async def _send_welcome_message(chat_profile: str) -> None:
    status_cards = build_status_cards(REPO_ROOT)
    welcome = build_welcome_markdown(chat_profile, status_cards)
    await cl.Message(
        content=welcome,
        actions=build_welcome_actions(chat_profile),
    ).send()


def _thread_metadata(thread: ThreadDict) -> dict[str, object]:
    metadata = thread.get("metadata") if isinstance(thread, dict) else {}
    return metadata if isinstance(metadata, dict) else {}


def _generate_thread_title(first_message: str) -> str:
    """Generate a readable thread title from the first user message.

    Extracts the first line, truncates to THREAD_TITLE_MAX_LENGTH,
    and adds ellipsis if truncated. Falls back to 'New conversation' for empty input.
    """
    if not first_message or not first_message.strip():
        return "New conversation"

    # Take first line only (remove newlines)
    first_line = first_message.strip().split("\n")[0].strip()

    # Truncate with ellipsis if too long
    if len(first_line) > THREAD_TITLE_MAX_LENGTH:
        return first_line[: THREAD_TITLE_MAX_LENGTH - 3].rstrip() + "..."

    return first_line if first_line else "New conversation"


async def _update_thread_title_from_message(thread_id: str, message_content: str) -> None:
    """Update thread title from first message if not already set."""
    from src.services.chainlit_data_layer import PostgreSQLChainlitDataLayer

    # Get the data layer from Chainlit's context - defensively handle missing attributes
    try:
        data_layer = getattr(cl, "data", None)
        if data_layer is None:
            return
        layer = getattr(data_layer, "_data_layer", None)
        if not isinstance(layer, PostgreSQLChainlitDataLayer):
            return
    except Exception:
        return

    try:
        # Check if thread already has a custom name
        thread = await layer.get_thread(thread_id)
        existing_name = thread.get("name") if thread else None

        # Only update if the name is empty, None, or looks auto-generated (UUID-like)
        needs_title = False
        if not existing_name:
            needs_title = True
        elif len(existing_name) == 36 and "-" in existing_name:
            # Looks like a UUID (default Chainlit thread ID)
            needs_title = True

        if needs_title:
            title = _generate_thread_title(message_content)
            await layer.update_thread(thread_id=thread_id, name=title)
            logger.debug("thread_title_set", thread_id=thread_id, title=title)
    except Exception as exc:
        # Don't fail the chat if title update fails
        logger.warning("thread_title_update_failed", thread_id=thread_id, error=str(exc))


@chainlit_server_app.middleware("http")
async def probe_endpoint_middleware(request: Request, call_next):
    """Serve probe endpoints before Chainlit's catch-all HTML route."""
    if request.url.path in PROBE_ENDPOINT_PATHS:
        if request.url.path.endswith("healthz"):
            return JSONResponse(status_code=200, content=await healthz())
        return await readinessz()

    return await call_next(request)


@chainlit_server_app.get("/project/healthz")
@chainlit_server_app.get("/healthz")
async def healthz():
    """Lightweight health endpoint for container probes."""
    return {"status": "ok", "service": "cdp-merged", "llm_provider": settings.LLM_PROVIDER}


def _database_config_source() -> str | None:
    """Report which runtime source will provide PostgreSQL connectivity."""
    return database_config_source(REPO_ROOT)


@chainlit_server_app.get("/project/readinessz")
@chainlit_server_app.get("/readinessz")
async def readinessz():
    """Probe the deployed chat runtime, including PostgreSQL-backed query readiness."""
    config_source = _database_config_source()

    checks: dict[str, dict[str, object]] = {
        "app": {
            "status": "ok",
            "service": "cdp-merged",
            "llm_provider": settings.LLM_PROVIDER,
        }
    }

    if not config_source:
        error = "DATABASE_URL is not configured and local .env.database is unavailable."
        checks["postgresql"] = {
            "status": "error",
            "configured": False,
            "error": error,
        }
        checks["tool_layer"] = {
            "status": "error",
            "backend": "postgresql",
            "error": error,
        }
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "cdp-merged",
                "checks": checks,
            },
        )

    try:
        search_service = get_search_service()
        probe = await search_service.readiness_probe()
    except Exception as exc:
        logger.error("readiness_probe_failed", error=str(exc))
        checks["postgresql"] = {
            "status": "error",
            "configured": True,
            "source": config_source,
            "error": str(exc),
        }
        checks["tool_layer"] = {
            "status": "error",
            "backend": "postgresql",
            "error": str(exc),
        }
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "cdp-merged",
                "checks": checks,
            },
        )

    checks["postgresql"] = {
        "status": "ok",
        "configured": True,
        "source": config_source,
        "companies_table": probe["companies_table"],
    }
    checks["tool_layer"] = {
        "status": "ok",
        "backend": probe["backend"],
        "query_plane": "ready",
    }
    # Verify action processing capability (basic import check)
    try:
        # Import check only - modules are already imported at module level
        # but we verify they can be accessed from this context
        _ = build_action_reply  # noqa: F841
        _ = build_welcome_actions  # noqa: F841
        checks["action_processing"] = {
            "status": "ok",
            "ui_actions_available": True,
        }
    except Exception as action_exc:
        checks["action_processing"] = {
            "status": "warning",
            "ui_actions_available": False,
            "error": str(action_exc),
        }

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": "cdp-merged",
            "checks": checks,
        },
    )


@chainlit_server_app.on_event("startup")
async def ensure_runtime_postgresql_support_schema() -> None:
    """Backfill local/runtime support tables for already-initialized databases."""
    if not _database_config_source():
        return

    try:
        search_service = get_search_service()
        await search_service.ensure_connected()
        ensured = await ensure_runtime_support_schema(search_service._client)
        logger.info("runtime_support_schema_startup", ensured=ensured)
    except Exception as exc:
        logger.warning("runtime_support_schema_startup_failed", error=str(exc))


@cl.set_chat_profiles
async def set_chat_profiles(_current_user=None, _language=None):
    """Expose role-specific chat profiles in the launcher."""
    return build_chat_profiles()


@cl.set_starters
async def set_starters(_current_user=None, _language=None):
    """Provide profile-aware starter prompts."""
    return build_starters(_safe_user_session_get("chat_profile"))


@cl.on_chat_start
async def start():
    """Initialize the chat session."""
    session_id = _safe_user_session_get("id")
    thread_id, chat_profile, profile_id = await _initialize_chat_session()

    logger.info(
        "session_started",
        session_id=session_id,
        thread_id=thread_id,
        profile_id=profile_id,
        chat_profile=chat_profile,
    )

    await _send_welcome_message(chat_profile)


@cl.on_chat_resume
async def resume_chat(thread: ThreadDict) -> None:
    """Rebind workflow/checkpointer state when Chainlit reopens an existing thread."""
    session_id = _safe_user_session_get("id")
    metadata = _thread_metadata(thread)
    thread_id, chat_profile, profile_id = await _initialize_chat_session(
        thread_id=str(thread.get("id") or _current_thread_id() or session_id or ""),
        chat_profile=str(metadata.get("chat_profile") or "") or None,
        profile_id_hint=str(metadata.get("profile_id") or "") or None,
    )

    logger.info(
        "session_resumed",
        session_id=session_id,
        thread_id=thread_id,
        profile_id=profile_id,
        chat_profile=chat_profile,
    )


@cl.on_chat_end
async def end():
    """Close the per-session checkpointer connection cleanly."""
    conn = cl.user_session.get("checkpointer_conn")
    if conn:
        await conn.close()
    clear_trace_id()


@cl.on_message
async def main(message: cl.Message):
    """Handle user messages."""
    workflow = cl.user_session.get("workflow")
    thread_id = cl.user_session.get("thread_id")
    profile_id = cl.user_session.get("profile_id")

    # Set thread title from first message if needed
    if thread_id:
        await _update_thread_title_from_message(thread_id, message.content)

    # ─── Session state validation ────────────────────────────────────────────
    if not workflow:
        logger.error("workflow_not_initialized", thread_id=thread_id)
        await cl.Message(
            content="❌ Chat session not properly initialized. Please refresh the page and try again."
        ).send()
        return

    if not thread_id:
        logger.error("thread_id_missing")
        await cl.Message(
            content="❌ Session ID not found. Please refresh the page and try again."
        ).send()
        return

    # Re-bind trace ID for this session
    trace_id = cl.user_session.get("trace_id") or str(uuid.uuid4())
    bind_trace_id(trace_id)

    # ─── Input length guard ──────────────────────────────────────────────────
    if len(message.content) > MAX_QUERY_LENGTH:
        ERRORS_TOTAL.labels(error_type="query_too_long").inc()
        logger.warning(
            "query_too_long",
            length=len(message.content),
            max=MAX_QUERY_LENGTH,
        )
        await cl.Message(
            content=f"❌ Query too long ({len(message.content)} chars). Maximum is {MAX_QUERY_LENGTH} characters."
        ).send()
        return

    logger.info("message_received", thread_id=thread_id, query_length=len(message.content))

    inputs = {
        "messages": [HumanMessage(content=message.content)],
        "language": "",
        "profile_id": profile_id,
    }
    config = {"configurable": {"thread_id": thread_id}}

    async with cl.Step(name="🔍 Processing Query", type="run") as step:
        final_answer = ""
        tool_calls = []
        msg = cl.Message(content="")

        try:
            async for event in workflow.astream_events(inputs, config=config, version="v2"):
                kind = event["event"]
                name = event.get("name")

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if getattr(chunk, "content", None) and isinstance(chunk.content, str):
                        await msg.stream_token(chunk.content)
                        final_answer += chunk.content
                elif kind == "on_tool_start":
                    if name and name != "agent":
                        tool_calls.append(name)

            step.output = (
                f"Used {len(tool_calls)} tool call(s) to process your query."
                if tool_calls
                else "Query processed directly."
            )
            QUERY_REQUESTS_TOTAL.labels(status="success").inc()
            logger.info("query_complete", tool_calls=len(tool_calls))

        except Exception as exc:
            step.is_error = True
            step.output = f"Error during processing: {exc}"
            QUERY_REQUESTS_TOTAL.labels(status="error").inc()
            ERRORS_TOTAL.labels(error_type=type(exc).__name__).inc()
            logger.error("query_error", error=str(exc), exc_info=exc)
            await cl.Message(content=f"❌ Sorry, I encountered an error: {exc}").send()
            return

    if final_answer:
        await msg.send()
    else:
        await cl.Message(
            content="I apologize, but I couldn't generate a response. Please try again."
        ).send()

    clear_trace_id()


async def _send_action_reply(action_name: str):
    """Send action reply with comprehensive error handling."""
    try:
        chat_profile = _safe_user_session_get("chat_profile") or DEFAULT_CHAT_PROFILE
        reply = build_action_reply(action_name, chat_profile, REPO_ROOT)
        await _safe_send_message(reply.content, reply.actions)
    except Exception as exc:
        logger.error("action_reply_failed", action=action_name, error=str(exc), exc_info=True)
        await _safe_send_message(
            "❌ Sorry, I couldn't process that action. Please try typing your request instead."
        )


async def _safe_send_message(content: str, actions: list[cl.Action] | None = None) -> None:
    """Attempt to send a Chainlit message without surfacing callback-breaking exceptions."""
    try:
        await cl.Message(content=content, actions=actions or []).send()
    except Exception as exc:
        logger.error("message_send_failed", error=str(exc), exc_info=True)


async def _run_action_callback(action_name: str, action) -> None:
    """Run callback logic and swallow edge-case send/context errors."""
    _ = action
    try:
        await _send_action_reply(action_name)
    except Exception as exc:
        logger.error(
            "action_callback_unhandled",
            action=action_name,
            error=str(exc),
            exc_info=True,
        )


@cl.action_callback("ui_search_companies")
async def on_search_companies(action):
    """Handle company-search quick action."""
    await _run_action_callback("ui_search_companies", action)


@cl.action_callback("ui_create_segment")
async def on_ui_create_segment(action):
    """Handle segment-design quick action."""
    await _run_action_callback("ui_create_segment", action)


@cl.action_callback("ui_view_analytics")
async def on_view_analytics(action):
    """Handle analytics quick action."""
    await _run_action_callback("ui_view_analytics", action)


@cl.action_callback("ui_show_status")
async def on_show_status(action):
    """Handle system-status quick action."""
    await _run_action_callback("ui_show_status", action)


@cl.action_callback("create_segment")
async def on_create_segment(action):
    """Handle segment creation action."""
    await _run_action_callback("ui_create_segment", action)


@cl.action_callback("push_to_resend")
async def on_push_to_resend(action):
    """Handle Resend push action."""
    await _run_action_callback("push_to_resend", action)


# ─── Artifact Download Endpoint ─────────────────────────────────────────────


@chainlit_server_app.get("/download/artifacts/{filename}")
async def download_artifact(filename: str):
    """Serve artifact files (CSV, JSON, Markdown) with path traversal protection.

    This endpoint allows users to download files created by the create_data_artifact tool.
    Path traversal attacks are prevented by validating the resolved path stays within
    the artifact root directory.

    Args:
        filename: Name of the artifact file to download (e.g., "report_20260307_181718.csv")

    Returns:
        FileResponse: The artifact file with appropriate content-type header

    Raises:
        HTTPException: 400 for invalid filenames, 403 for path traversal attempts,
                      404 if file doesn't exist
    """
    # Reject path traversal attempts in the filename itself
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Resolve the full path and ensure it's within ARTIFACT_ROOT
    try:
        file_path = (ARTIFACT_ROOT / filename).resolve()
        root_path = ARTIFACT_ROOT.resolve()

        # Security check: file must be within ARTIFACT_ROOT
        if not str(file_path).startswith(str(root_path)):
            raise HTTPException(status_code=403, detail="Access denied")
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid path: {exc}") from exc

    # Check file exists
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Check it's actually a file (not a directory)
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    # Determine content type based on extension
    suffix = file_path.suffix.lower()
    media_types = {
        ".csv": "text/csv",
        ".json": "application/json",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )
