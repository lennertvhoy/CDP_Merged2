"""Persistence, evaluation, and notification helpers for operator-shell feedback."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import asyncpg
from fastapi import UploadFile
from pydantic import BaseModel, Field

from src.config import settings
from src.core.database_url import resolve_database_url
from src.core.llm_provider import get_llm_provider
from src.core.logger import get_logger
from src.services.resend import ResendClient
from src.services.runtime_support_schema import ensure_runtime_support_schema

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "output" / "operator_feedback"
MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
SENSITIVE_KEY_MARKERS = (
    "password",
    "secret",
    "token",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
)


class FeedbackEvaluationResult(BaseModel):
    category: Literal[
        "bug",
        "ux",
        "performance",
        "data_quality",
        "feature_request",
        "question",
        "other",
    ] = "other"
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    reproducibility: Literal["unknown", "intermittent", "consistent"] = "unknown"
    impacted_area: str = "operator-shell"
    more_info_needed: bool = False
    suggested_next_action: str = (
        "Review the report, reproduce it locally, and decide whether a code fix is needed."
    )
    summary: str = "Operator feedback received."
    rationale: str = "Automatic evaluation did not add more detail."


class FeedbackAttachmentRecord(BaseModel):
    attachment_id: str
    file_name: str
    content_type: str | None = None
    byte_size: int
    storage_path: str


class FeedbackSubmissionResult(BaseModel):
    status: Literal["accepted"] = "accepted"
    feedback_id: str
    evaluation_status: str
    notification_status: str
    attachments: list[FeedbackAttachmentRecord] = Field(default_factory=list)


@dataclass(slots=True)
class FeedbackSubmission:
    surface: str
    feedback_text: str
    page_path: str | None = None
    page_url: str | None = None
    thread_id: str | None = None
    company_ref: str | None = None
    segment_ref: str | None = None
    context: dict[str, Any] | None = None
    user_identifier: str | None = None
    user_display_name: str | None = None


def _compact(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def sanitize_feedback_context(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
                continue
            cleaned[str(key)] = sanitize_feedback_context(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_feedback_context(item) for item in value]
    if isinstance(value, str):
        return value.strip()
    return value


def heuristic_feedback_evaluation(submission: FeedbackSubmission) -> FeedbackEvaluationResult:
    text = submission.feedback_text.lower()
    category = "other"
    severity = "medium"
    reproducibility = "unknown"
    impacted_area = submission.surface
    more_info_needed = False
    next_action = "Review the report, reproduce it locally, and confirm the affected shell path."
    rationale_bits = ["Matched fallback heuristics against the feedback text and current surface."]

    if any(token in text for token in ("error", "bug", "broken", "failed", "fail")):
        category = "bug"
        severity = "high"
        next_action = (
            "Reproduce the failure on localhost:3000 and inspect the backing API/runtime logs."
        )
    elif any(token in text for token in ("slow", "lag", "timeout", "time out", "stuck", "freeze")):
        category = "performance"
        severity = (
            "high"
            if any(t in text for t in ("timeout", "time out", "times out", "stuck"))
            else "medium"
        )
        next_action = (
            "Check recent runtime latency on the affected shell path and reproduce the slow step."
        )
    elif any(token in text for token in ("wrong", "incorrect", "count", "data", "mismatch")):
        category = "data_quality"
        severity = "high" if "wrong" in text or "incorrect" in text else "medium"
        next_action = "Compare the reported result against PostgreSQL truth and inspect the query/tool trace."
    elif any(token in text for token in ("feature", "missing", "wish", "would like")):
        category = "feature_request"
        severity = "low"
        next_action = "Review whether the request belongs in the active shell-hardening backlog."
    elif any(token in text for token in ("confusing", "unclear", "hard", "ux", "copy")):
        category = "ux"
        severity = "medium"
        next_action = "Review the relevant shell copy and interaction flow with a browser repro."
    elif "?" in text:
        category = "question"
        severity = "low"
        next_action = (
            "Confirm whether the report needs a product explanation or a real code change."
        )

    # Check intermittent first - "not always" should not trigger consistent
    if any(token in text for token in ("sometimes", "intermittent", "occasionally")):
        reproducibility = "intermittent"
    elif any(token in text for token in ("always", "every time", "consistently")):
        reproducibility = "consistent"

    if any(token in text for token in ("not sure", "unclear", "maybe", "i think")):
        more_info_needed = True
        rationale_bits.append("Reporter language suggests extra repro detail may still be needed.")

    summary = submission.feedback_text.strip()
    if len(summary) > 180:
        summary = summary[:177].rstrip() + "..."

    return FeedbackEvaluationResult(
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        reproducibility=reproducibility,  # type: ignore[arg-type]
        impacted_area=impacted_area,
        more_info_needed=more_info_needed,
        suggested_next_action=next_action,
        summary=summary or "Operator feedback received.",
        rationale=" ".join(rationale_bits),
    )


def _safe_filename(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return sanitized or "attachment"


def _notification_configured() -> bool:
    return bool(settings.RESEND_API_KEY and settings.OPERATOR_FEEDBACK_NOTIFY_TO)


def build_notification_email(
    *,
    submission: FeedbackSubmission,
    feedback_id: str,
    evaluation: FeedbackEvaluationResult | None,
    attachments: list[FeedbackAttachmentRecord],
) -> tuple[str, str]:
    subject = f"{settings.OPERATOR_FEEDBACK_SUBJECT_PREFIX} {submission.surface} {feedback_id[:8]}"
    summary = evaluation.summary if evaluation else submission.feedback_text.strip()
    impacted_area = evaluation.impacted_area if evaluation else submission.surface
    severity = evaluation.severity if evaluation else "unknown"
    category = evaluation.category if evaluation else "unknown"
    repro = evaluation.reproducibility if evaluation else "unknown"
    more_info = "yes" if evaluation and evaluation.more_info_needed else "no"
    attachment_lines = (
        "".join(
            f"<li><code>{attachment.file_name}</code> ({attachment.byte_size} bytes) -> <code>{attachment.storage_path}</code></li>"
            for attachment in attachments
        )
        or "<li>No screenshot attachments</li>"
    )
    html = f"""
    <h2>Operator feedback received</h2>
    <p><strong>ID:</strong> {feedback_id}</p>
    <p><strong>User:</strong> {submission.user_identifier or "anonymous"}</p>
    <p><strong>Surface:</strong> {submission.surface}</p>
    <p><strong>Page:</strong> {submission.page_path or "-"}</p>
    <p><strong>Thread:</strong> {submission.thread_id or "-"}</p>
    <p><strong>Summary:</strong> {summary}</p>
    <p><strong>Category:</strong> {category} | <strong>Severity:</strong> {severity} | <strong>Reproducibility:</strong> {repro}</p>
    <p><strong>Impacted area:</strong> {impacted_area}</p>
    <p><strong>More info needed:</strong> {more_info}</p>
    <p><strong>Suggested next action:</strong> {evaluation.suggested_next_action if evaluation else "Review the report manually."}</p>
    <h3>Feedback text</h3>
    <pre>{submission.feedback_text}</pre>
    <h3>Attachments</h3>
    <ul>{attachment_lines}</ul>
    """
    return subject, html


class OperatorFeedbackStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or resolve_database_url(REPO_ROOT)
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self.pool is not None:
            return
        await ensure_runtime_support_schema(connection_url=self.database_url)
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=5,
            command_timeout=60,
        )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def create_feedback(
        self,
        *,
        feedback_id: str,
        submission: FeedbackSubmission,
        attachments: list[FeedbackAttachmentRecord],
    ) -> None:
        await self.connect()
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO operator_feedback (
                        feedback_id,
                        user_identifier,
                        user_display_name,
                        surface,
                        page_path,
                        page_url,
                        thread_id,
                        company_ref,
                        segment_ref,
                        feedback_text,
                        context_json
                    )
                    VALUES (
                        $1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb
                    )
                    """,
                    feedback_id,
                    submission.user_identifier,
                    submission.user_display_name,
                    submission.surface,
                    submission.page_path,
                    submission.page_url,
                    submission.thread_id,
                    submission.company_ref,
                    submission.segment_ref,
                    submission.feedback_text,
                    json.dumps(submission.context or {}),
                )
                for attachment in attachments:
                    await conn.execute(
                        """
                        INSERT INTO operator_feedback_attachments (
                            attachment_id,
                            feedback_id,
                            file_name,
                            content_type,
                            byte_size,
                            storage_path
                        )
                        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6)
                        """,
                        attachment.attachment_id,
                        feedback_id,
                        attachment.file_name,
                        attachment.content_type,
                        attachment.byte_size,
                        attachment.storage_path,
                    )

    async def update_evaluation(
        self,
        *,
        feedback_id: str,
        status: str,
        method: str | None,
        evaluation: FeedbackEvaluationResult | None,
        error: str | None = None,
    ) -> None:
        await self.connect()
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE operator_feedback
                SET evaluation_status = $2,
                    evaluation_method = $3,
                    evaluation_json = $4::jsonb,
                    evaluation_error = $5,
                    updated_at = CURRENT_TIMESTAMP
                WHERE feedback_id = $1::uuid
                """,
                feedback_id,
                status,
                method,
                json.dumps(evaluation.model_dump()) if evaluation else None,
                error,
            )

    async def update_notification(
        self,
        *,
        feedback_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        await self.connect()
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE operator_feedback
                SET notification_status = $2,
                    notification_error = $3,
                    updated_at = CURRENT_TIMESTAMP
                WHERE feedback_id = $1::uuid
                """,
                feedback_id,
                status,
                error,
            )


async def save_feedback_attachments(
    feedback_id: str,
    screenshots: list[UploadFile] | None,
) -> list[FeedbackAttachmentRecord]:
    saved: list[FeedbackAttachmentRecord] = []
    files = screenshots or []
    if len(files) > MAX_ATTACHMENTS:
        raise ValueError(f"At most {MAX_ATTACHMENTS} screenshot attachments are allowed.")

    feedback_dir = OUTPUT_ROOT / feedback_id
    feedback_dir.mkdir(parents=True, exist_ok=True)

    for upload in files:
        content_type = upload.content_type or ""
        if content_type and not content_type.startswith("image/"):
            raise ValueError("Only image screenshot uploads are supported.")
        raw = await upload.read()
        if len(raw) > MAX_ATTACHMENT_BYTES:
            raise ValueError(
                f"Screenshot '{upload.filename or 'attachment'}' exceeds the 5 MB limit."
            )
        attachment_id = str(uuid.uuid4())
        file_name = _safe_filename(upload.filename or f"{attachment_id}.png")
        target = feedback_dir / file_name
        target.write_bytes(raw)
        saved.append(
            FeedbackAttachmentRecord(
                attachment_id=attachment_id,
                file_name=file_name,
                content_type=upload.content_type,
                byte_size=len(raw),
                storage_path=str(target.relative_to(REPO_ROOT)),
            )
        )

    return saved


async def evaluate_feedback(
    submission: FeedbackSubmission,
) -> tuple[str, str, FeedbackEvaluationResult]:
    heuristic = heuristic_feedback_evaluation(submission)
    try:
        provider = get_llm_provider()
        messages = [
            {
                "role": "system",
                "content": (
                    "Classify operator-shell feedback into a compact engineering triage record. "
                    "Prefer factual summaries, severity based on operator impact, and next actions "
                    "that a developer can execute."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    _compact(
                        {
                            "surface": submission.surface,
                            "page_path": submission.page_path,
                            "thread_id": submission.thread_id,
                            "company_ref": submission.company_ref,
                            "segment_ref": submission.segment_ref,
                            "feedback_text": submission.feedback_text,
                            "context": submission.context or {},
                        }
                    ),
                    ensure_ascii=True,
                ),
            },
        ]
        evaluation = await provider.generate_structured(
            messages=messages,
            response_model=FeedbackEvaluationResult,
            temperature=0.0,
        )
        if not isinstance(evaluation, FeedbackEvaluationResult):
            evaluation = FeedbackEvaluationResult.model_validate(evaluation)
        if not evaluation.summary.strip():
            evaluation.summary = heuristic.summary
        if not evaluation.suggested_next_action.strip():
            evaluation.suggested_next_action = heuristic.suggested_next_action
        return ("completed", "llm", evaluation)
    except Exception as exc:
        logger.warning("operator_feedback_evaluation_fallback", error=str(exc))
        return ("fallback", "heuristic", heuristic)


async def notify_feedback(
    *,
    submission: FeedbackSubmission,
    feedback_id: str,
    evaluation: FeedbackEvaluationResult | None,
    attachments: list[FeedbackAttachmentRecord],
) -> tuple[str, str | None]:
    if not _notification_configured():
        return ("skipped", "Resend notification is not configured.")

    subject, html = build_notification_email(
        submission=submission,
        feedback_id=feedback_id,
        evaluation=evaluation,
        attachments=attachments,
    )
    try:
        client = ResendClient()
        await client.send_email(
            to=str(settings.OPERATOR_FEEDBACK_NOTIFY_TO),
            subject=subject,
            html=html,
        )
        return ("sent", None)
    except Exception as exc:
        logger.warning(
            "operator_feedback_notification_failed", feedback_id=feedback_id, error=str(exc)
        )
        return ("failed", str(exc))


async def submit_operator_feedback(
    *,
    submission: FeedbackSubmission,
    screenshots: list[UploadFile] | None = None,
) -> FeedbackSubmissionResult:
    cleaned_text = submission.feedback_text.strip()
    if not cleaned_text:
        raise ValueError("Feedback text is required.")

    feedback_id = str(uuid.uuid4())
    cleaned_context = sanitize_feedback_context(submission.context or {})
    prepared_submission = FeedbackSubmission(
        surface=submission.surface.strip() or "unknown",
        feedback_text=cleaned_text,
        page_path=submission.page_path,
        page_url=submission.page_url,
        thread_id=submission.thread_id,
        company_ref=submission.company_ref,
        segment_ref=submission.segment_ref,
        context=cleaned_context,
        user_identifier=submission.user_identifier,
        user_display_name=submission.user_display_name,
    )

    attachments = await save_feedback_attachments(feedback_id, screenshots)
    store = OperatorFeedbackStore()
    try:
        await store.create_feedback(
            feedback_id=feedback_id,
            submission=prepared_submission,
            attachments=attachments,
        )

        evaluation_status = "pending"
        notification_status = "pending"
        evaluation: FeedbackEvaluationResult | None = None

        try:
            evaluation_status, evaluation_method, evaluation = await evaluate_feedback(
                prepared_submission
            )
            await store.update_evaluation(
                feedback_id=feedback_id,
                status=evaluation_status,
                method=evaluation_method,
                evaluation=evaluation,
            )
        except Exception as exc:
            evaluation_status = "failed"
            await store.update_evaluation(
                feedback_id=feedback_id,
                status=evaluation_status,
                method=None,
                evaluation=None,
                error=str(exc),
            )

        notification_status, notification_error = await notify_feedback(
            submission=prepared_submission,
            feedback_id=feedback_id,
            evaluation=evaluation,
            attachments=attachments,
        )
        await store.update_notification(
            feedback_id=feedback_id,
            status=notification_status,
            error=notification_error,
        )

        return FeedbackSubmissionResult(
            feedback_id=feedback_id,
            evaluation_status=evaluation_status,
            notification_status=notification_status,
            attachments=attachments,
        )
    finally:
        await store.close()


__all__ = [
    "FeedbackAttachmentRecord",
    "FeedbackEvaluationResult",
    "FeedbackSubmission",
    "FeedbackSubmissionResult",
    "OperatorFeedbackStore",
    "build_notification_email",
    "heuristic_feedback_evaluation",
    "sanitize_feedback_context",
    "submit_operator_feedback",
]
