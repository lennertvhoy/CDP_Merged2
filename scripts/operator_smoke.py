"""Seed, reset, and run the first operator-shell smoke baseline.

WARNING: This script uses generic Playwright with spawned Chromium:
  browser = playwright.chromium.launch(headless=not headed)

For the project's canonical attached-Edge/CDP path, see:
  - scripts/mcp_cdp_helper.py (MCPBrowserController)
  - tests/e2e/test_attached_edge_cdp_smoke.py

Architecture: ISOLATED_PLAYWRIGHT (historical, non-canonical)
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import traceback
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

import asyncpg
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).parent.parent.resolve()
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO_ROOT))

from src.core.database_url import resolve_database_url
from src.core.runtime_env import bootstrap_runtime_environment

bootstrap_runtime_environment()

from src.services.local_account_auth import (
    LocalAccountExistsError,
    LocalAccountNotFoundError,
    LocalAccountStore,
)
from src.services.operator_smoke import (
    SMOKE_ACCOUNT_SPECS,
    classify_public_root_response,
    count_prompt,
    detect_public_base_url,
    detect_tool_leakage,
    load_smoke_passwords,
    local_base_url,
    looks_like_answer_first_count_reply,
    ready_prompt,
)

OUTPUT_ROOT = REPO_ROOT / "output" / "operator_smoke"
THREADS_ENDPOINT = "/operator-api/threads"
BOOTSTRAP_ENDPOINT = "/operator-api/bootstrap"
LOGIN_ENDPOINT = "/operator-api/auth/login"
CHAT_TEXTAREA_PLACEHOLDER = "Ask a question, continue this conversation, or start a new topic..."
RUN_TIMEOUT_MS = 90_000


@dataclass
class CaseResult:
    case_id: str
    scope: str
    status: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def format_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ").lower()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seed deterministic operator smoke accounts, reset their state, and run "
            "SMK-01 through SMK-09 against the live host-managed shell path."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed = subparsers.add_parser("seed", help="Create/rotate the deterministic smoke accounts")
    seed.add_argument("--reset-threads", action="store_true", help="Delete existing smoke threads")

    reset = subparsers.add_parser("reset", help="Delete smoke threads and local smoke artifacts")
    reset.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep output/operator_smoke artifacts while clearing database state",
    )

    run = subparsers.add_parser("run", help="Run the operator smoke baseline")
    run.add_argument(
        "--scope",
        choices=("local", "public", "all"),
        default="all",
        help="Which smoke scope to execute",
    )
    run.add_argument("--skip-reset", action="store_true", help="Do not clear prior smoke state first")
    run.add_argument("--headed", action="store_true", help="Show the browser during local smoke")
    run.add_argument(
        "--output-dir",
        help="Optional output directory for JSON and screenshots (defaults to output/operator_smoke/<run-id>)",
    )

    return parser


def make_output_dir(requested: str | None) -> Path:
    if requested:
        path = Path(requested)
        if not path.is_absolute():
            path = REPO_ROOT / path
    else:
        path = OUTPUT_ROOT / format_run_id()
    path.mkdir(parents=True, exist_ok=True)
    return path


async def seed_smoke_accounts(*, reset_threads: bool) -> list[str]:
    passwords = load_smoke_passwords()
    store = LocalAccountStore()
    actions: list[str] = []
    try:
        for spec in SMOKE_ACCOUNT_SPECS:
            password = passwords[spec.identifier]
            try:
                await store.create_account(
                    identifier=spec.identifier,
                    display_name=spec.display_name,
                    password=password,
                )
                actions.append(f"created:{spec.identifier}")
            except LocalAccountExistsError:
                await store.update_password(spec.identifier, password)
                actions.append(f"password-rotated:{spec.identifier}")
            try:
                await store.set_account_active(spec.identifier, is_active=True)
            except LocalAccountNotFoundError:
                pass
            else:
                actions.append(f"activated:{spec.identifier}")
    finally:
        await store.close()

    if reset_threads:
        deleted = await reset_smoke_threads()
        actions.append(f"threads-deleted:{deleted}")

    return actions


async def reset_smoke_threads() -> int:
    database_url = resolve_database_url(REPO_ROOT)
    identifiers = [spec.identifier for spec in SMOKE_ACCOUNT_SPECS]
    conn = await asyncpg.connect(database_url, command_timeout=60)
    try:
        deleted = await conn.fetchval(
            """
            WITH deleted AS (
                DELETE FROM app_chat_threads t
                USING app_chat_users u
                WHERE t.user_id = u.user_id
                  AND u.identifier = ANY($1::text[])
                RETURNING t.thread_id
            )
            SELECT COUNT(*)::int FROM deleted
            """,
            identifiers,
        )
    finally:
        await conn.close()
    return int(deleted or 0)


def reset_smoke_artifacts() -> int:
    if not OUTPUT_ROOT.exists():
        return 0
    removed = 0
    for child in OUTPUT_ROOT.iterdir():
        removed += 1
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return removed


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def http_json(
    opener,
    *,
    url: str,
    method: str = "GET",
    data: dict[str, str] | None = None,
) -> tuple[int, Any]:
    encoded = None
    headers: dict[str, str] = {}
    if data is not None:
        encoded = urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = Request(url, data=encoded, method=method, headers=headers)
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return exc.code, parsed


def http_text(opener, *, url: str, method: str = "GET") -> tuple[int, dict[str, str], str]:
    request = Request(url, method=method)
    try:
        with opener.open(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, dict(response.headers.items()), body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), body


def page_fetch(page, path: str) -> dict[str, Any]:
    return page.evaluate(
        """
        async (path) => {
          const response = await fetch(path, { credentials: "same-origin", cache: "no-store" });
          const text = await response.text();
          let body = text;
          try {
            body = JSON.parse(text);
          } catch (_error) {
            body = text;
          }
          return {
            status: response.status,
            body,
            contentType: response.headers.get("content-type") || "",
          };
        }
        """,
        path,
    )


def click_sidebar(page, label: str) -> None:
    page.get_by_role("button", name=label, exact=True).click()
    page.get_by_text(label, exact=True).wait_for(timeout=10_000)


def wait_for_send_ready(page) -> None:
    page.get_by_role("button", name="Send").wait_for(timeout=RUN_TIMEOUT_MS)
    page.get_by_role("button", name="Send").is_enabled()


def last_assistant_output(thread_detail: dict[str, Any]) -> str:
    steps = thread_detail.get("thread", {}).get("steps", [])
    outputs = [
        str(step.get("output") or "")
        for step in steps
        if step.get("type") == "assistant_message" and step.get("output")
    ]
    return outputs[-1] if outputs else ""


def ensure_login(page, *, identifier: str, password: str) -> None:
    page.get_by_text("Private Access", exact=True).wait_for(timeout=15_000)
    page.get_by_placeholder("colleague@example.com").fill(identifier)
    page.locator('input[type="password"]').fill(password)
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="Chat", exact=True).wait_for(timeout=20_000)


def run_local_smoke(*, base_url: str, output_dir: Path, headed: bool) -> list[CaseResult]:
    passwords = load_smoke_passwords()
    user_a = SMOKE_ACCOUNT_SPECS[0]
    user_b = SMOKE_ACCOUNT_SPECS[1]
    ready_text = ready_prompt()
    count_text = count_prompt()
    results: list[CaseResult] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)

        context_a = browser.new_context(base_url=base_url)
        page_a = context_a.new_page()
        page_a.goto(base_url, wait_until="domcontentloaded")
        page_a.get_by_text("Private Access", exact=True).wait_for(timeout=15_000)

        gate_visible = page_a.get_by_text("Private Access", exact=True).is_visible()
        full_shell_hidden = page_a.get_by_role("button", name="Threads", exact=True).count() == 0
        gate_artifact = output_dir / "SMK-01-local-gate.png"
        page_a.screenshot(path=str(gate_artifact), full_page=True)
        results.append(
            CaseResult(
                case_id="SMK-01",
                scope="local",
                status="passed" if gate_visible and full_shell_hidden else "failed",
                summary=(
                    "Unauthenticated shell showed the private access gate only."
                    if gate_visible and full_shell_hidden
                    else "Unauthenticated shell did not stay on the expected gate-only surface."
                ),
                evidence=[
                    f"goto {base_url}",
                    "checked gate text and absence of authenticated shell navigation",
                ],
                artifacts=[str(gate_artifact.relative_to(REPO_ROOT))],
            )
        )

        ensure_login(page_a, identifier=user_a.identifier, password=passwords[user_a.identifier])
        bootstrap_after_login = page_fetch(page_a, BOOTSTRAP_ENDPOINT)
        login_artifact = output_dir / "SMK-02-local-login.png"
        page_a.screenshot(path=str(login_artifact), full_page=True)
        logged_in_ok = (
            bootstrap_after_login["status"] == 200
            and isinstance(bootstrap_after_login["body"], dict)
            and bootstrap_after_login["body"].get("phase") == "app"
            and bootstrap_after_login["body"].get("session", {}).get("authenticated") is True
            and bootstrap_after_login["body"].get("session", {}).get("user", {}).get("identifier")
            == user_a.identifier
        )
        results.append(
            CaseResult(
                case_id="SMK-02",
                scope="local",
                status="passed" if logged_in_ok else "failed",
                summary=(
                    "Local login succeeded and bootstrap returned an authenticated app session."
                    if logged_in_ok
                    else "Login or authenticated bootstrap failed after the local sign-in flow."
                ),
                evidence=[
                    "submitted access gate form in browser",
                    f"GET {BOOTSTRAP_ENDPOINT} via authenticated browser context",
                ],
                artifacts=[str(login_artifact.relative_to(REPO_ROOT))],
                details={"bootstrap": bootstrap_after_login["body"]},
            )
        )

        chat_box = page_a.get_by_placeholder(CHAT_TEXTAREA_PLACEHOLDER)
        chat_box.fill(ready_text)
        page_a.get_by_role("button", name="Send").click()
        wait_for_send_ready(page_a)

        thread_list_after_chat = page_fetch(page_a, THREADS_ENDPOINT)
        threads_payload = thread_list_after_chat["body"] if isinstance(thread_list_after_chat["body"], dict) else {}
        threads = threads_payload.get("threads", []) if isinstance(threads_payload, dict) else []
        thread_id = threads[0]["id"] if threads else None
        thread_created = bool(thread_id)
        create_artifact = output_dir / "SMK-03-thread-create.png"
        page_a.screenshot(path=str(create_artifact), full_page=True)
        results.append(
            CaseResult(
                case_id="SMK-03",
                scope="local",
                status="passed" if thread_created else "failed",
                summary=(
                    f"Authenticated chat created stored thread {thread_id}."
                    if thread_created
                    else "Authenticated chat did not produce a stored thread."
                ),
                evidence=[
                    f"submitted browser chat prompt: {ready_text}",
                    f"GET {THREADS_ENDPOINT} via authenticated browser context",
                ],
                artifacts=[str(create_artifact.relative_to(REPO_ROOT))],
                details={"thread_id": thread_id, "threads": threads[:3]},
            )
        )

        thread_detail_response = (
            page_fetch(page_a, f"{THREADS_ENDPOINT}/{thread_id}")
            if thread_id
            else {"status": 0, "body": {}}
        )
        ready_reply = (
            last_assistant_output(thread_detail_response["body"])
            if isinstance(thread_detail_response["body"], dict)
            else ""
        )
        ready_ok = thread_detail_response["status"] == 200 and "READY" in ready_reply.upper()
        ready_artifact = output_dir / "SMK-05-chat-turn.png"
        page_a.screenshot(path=str(ready_artifact), full_page=True)
        results.append(
            CaseResult(
                case_id="SMK-05",
                scope="local",
                status="passed" if ready_ok else "failed",
                summary=(
                    "One real chat turn completed on the live backend path."
                    if ready_ok
                    else "The real chat turn did not return the expected READY response."
                ),
                evidence=[
                    f"GET {THREADS_ENDPOINT}/{thread_id} after the first browser chat turn"
                    if thread_id
                    else "thread id unavailable after first browser chat turn",
                ],
                artifacts=[str(ready_artifact.relative_to(REPO_ROOT))],
                details={"thread_id": thread_id, "assistant_output": ready_reply},
            )
        )

        thread_resume_ok = False
        thread_resume_detail: dict[str, Any] = {"thread_id": thread_id}
        if thread_id:
            click_sidebar(page_a, "Threads")
            page_a.get_by_role("button", name="Resume in chat").click()
            page_a.get_by_role("button", name="Chat", exact=True).wait_for(timeout=10_000)
            page_a.get_by_text("Saved conversation", exact=True).wait_for(timeout=10_000)
            thread_resume_ok = page_a.get_by_text(ready_text, exact=True).count() > 0
            thread_resume_detail["detail_status"] = thread_detail_response["status"]
        resume_artifact = output_dir / "SMK-04-thread-resume.png"
        page_a.screenshot(path=str(resume_artifact), full_page=True)
        results.append(
            CaseResult(
                case_id="SMK-04",
                scope="local",
                status="passed" if thread_resume_ok else "failed",
                summary=(
                    "Thread list/detail/resume succeeded in the authenticated shell."
                    if thread_resume_ok
                    else "Thread detail/resume did not return to the same saved conversation."
                ),
                evidence=[
                    "opened Threads tab in browser",
                    "clicked Resume in chat on the stored conversation",
                ],
                artifacts=[str(resume_artifact.relative_to(REPO_ROOT))],
                details=thread_resume_detail,
            )
        )

        click_sidebar(page_a, "Chat")
        chat_box = page_a.get_by_placeholder(CHAT_TEXTAREA_PLACEHOLDER)
        chat_box.fill(count_text)
        page_a.get_by_role("button", name="Send").click()
        wait_for_send_ready(page_a)
        count_detail_response = (
            page_fetch(page_a, f"{THREADS_ENDPOINT}/{thread_id}")
            if thread_id
            else {"status": 0, "body": {}}
        )
        count_reply = (
            last_assistant_output(count_detail_response["body"])
            if isinstance(count_detail_response["body"], dict)
            else ""
        )
        leakage = detect_tool_leakage(count_reply)
        formatting_ok = bool(count_reply) and looks_like_answer_first_count_reply(count_reply) and not leakage
        formatting_artifact = output_dir / "SMK-06-count-formatting.png"
        page_a.screenshot(path=str(formatting_artifact), full_page=True)
        results.append(
            CaseResult(
                case_id="SMK-06",
                scope="local",
                status="passed" if formatting_ok else "failed",
                summary=(
                    "Count-answer formatting stayed answer-first without raw tool/debug leakage."
                    if formatting_ok
                    else "Count-answer formatting still exposed raw tool/debug leakage or lacked an answer-first lead."
                ),
                evidence=[
                    f"submitted browser count prompt: {count_text}",
                    f"checked final assistant output on {THREADS_ENDPOINT}/{thread_id}",
                ],
                artifacts=[str(formatting_artifact.relative_to(REPO_ROOT))],
                details={"assistant_output": count_reply, "tool_leakage": leakage},
            )
        )

        context_b = browser.new_context(base_url=base_url)
        page_b = context_b.new_page()
        page_b.goto(base_url, wait_until="domcontentloaded")
        ensure_login(page_b, identifier=user_b.identifier, password=passwords[user_b.identifier])
        page_b.get_by_role("button", name="Threads", exact=True).click()
        list_as_b = page_fetch(page_b, THREADS_ENDPOINT)
        thread_ids_as_b = [
            thread.get("id")
            for thread in list_as_b.get("body", {}).get("threads", [])
            if isinstance(thread, dict)
        ]
        detail_as_b = (
            page_fetch(page_b, f"{THREADS_ENDPOINT}/{thread_id}")
            if thread_id
            else {"status": 0, "body": {"detail": "Missing thread id from user A"}}
        )
        denied = detail_as_b["status"] in {403, 404} and thread_id not in thread_ids_as_b
        isolation_artifact = output_dir / "SMK-07-cross-user-isolation.png"
        page_b.screenshot(path=str(isolation_artifact), full_page=True)
        results.append(
            CaseResult(
                case_id="SMK-07",
                scope="local",
                status="passed" if denied else "failed",
                summary=(
                    "User B could not list or open user A's thread."
                    if denied
                    else "User B could still see or open user A's thread."
                ),
                evidence=[
                    "signed in with second deterministic smoke account",
                    f"GET {THREADS_ENDPOINT} and {THREADS_ENDPOINT}/{thread_id} as user B",
                ],
                artifacts=[str(isolation_artifact.relative_to(REPO_ROOT))],
                details={
                    "thread_ids_as_b": thread_ids_as_b,
                    "detail_status": detail_as_b["status"],
                    "detail_body": detail_as_b["body"],
                },
            )
        )

        # SMK-10: Feedback submission flow (after user A is logged in)
        page_a.get_by_role("button", name="Chat", exact=True).click()
        page_a.get_by_placeholder("Ask a question").wait_for(timeout=10_000)
        # Click global feedback button in sidebar
        page_a.locator("button[title=\"Share feedback\"]").first.click()
        page_a.get_by_text("Be specific about what broke").wait_for(timeout=10_000)
        # Fill feedback form
        feedback_text = "Smoke test feedback - verifying the feedback loop submission and notification flow."
        page_a.locator("textarea[placeholder*=\"Be specific\"]").fill(feedback_text)
        # Submit feedback
        page_a.get_by_role("button", name="Send feedback").click()
        # Wait for result
        page_a.get_by_text("Feedback saved as").wait_for(timeout=15_000)
        result_text = page_a.get_by_text("Feedback saved as").inner_text()
        feedback_ok = "Evaluation:" in result_text and "Notification:" in result_text
        feedback_artifact = output_dir / "SMK-10-feedback-submission.png"
        page_a.screenshot(path=str(feedback_artifact), full_page=True)
        results.append(
            CaseResult(
                case_id="SMK-10",
                scope="local",
                status="passed" if feedback_ok else "failed",
                summary="Feedback submitted successfully with evaluation and notification status." if feedback_ok else "Feedback submission did not return expected status.",
                evidence=[
                    "clicked global feedback button in sidebar",
                    "filled feedback form with smoke test text",
                    "submitted and received feedback confirmation",
                ],
                artifacts=[str(feedback_artifact.relative_to(REPO_ROOT))],
                details={"result_text": result_text},
            )
        )

        context_b.close()
        context_a.close()
        browser.close()

    return results


def run_preview_continuity_check(*, output_dir: Path) -> list[CaseResult]:
    """SMK-11: Verify preview continuity scripts and public URL discovery."""
    results: list[CaseResult] = []
    
    # Check if preview health script exists and is executable
    health_script = REPO_ROOT / "scripts" / "check_preview_health.sh"
    url_script = REPO_ROOT / "scripts" / "get_public_preview_url.sh"
    verify_script = REPO_ROOT / "scripts" / "verify_public_preview.sh"
    
    scripts_exist = all(
        script.exists() and script.is_file()
        for script in [health_script, url_script, verify_script]
    )
    
    # Try to get public URL
    public_url = ""
    url_ok = False
    try:
        result = subprocess.run(
            [str(url_script)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            public_url = result.stdout.strip()
            url_ok = bool(public_url) and public_url.startswith("https://")
    except Exception:
        pass
    
    # Run health check if scripts exist
    health_ok = False
    health_output = ""
    if scripts_exist:
        try:
            result = subprocess.run(
                [str(health_script)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            health_ok = result.returncode == 0
            health_output = result.stdout
        except Exception as exc:
            health_output = str(exc)
    
    # Check for watchdog state file
    state_file = REPO_ROOT / ".preview_state.json"
    state_ok = False
    state_age_seconds = None
    if state_file.exists():
        try:
            state_data = json.loads(state_file.read_text())
            if state_data.get("status") in ("healthy", "recovered"):
                checked_at = state_data.get("checked_at", "")
                if checked_at:
                    # Parse ISO timestamp
                    try:
                        from datetime import datetime
                        checked_time = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
                        now = datetime.now(UTC)
                        state_age_seconds = (now - checked_time).total_seconds()
                        state_ok = state_age_seconds < 300  # Within 5 minutes
                    except Exception:
                        state_ok = True  # Assume OK if we can't parse
        except Exception:
            pass
    
    continuity_ok = scripts_exist and url_ok and health_ok
    
    # Save artifact
    artifact_path = output_dir / "SMK-11-preview-continuity.json"
    save_json(
        artifact_path,
        {
            "scripts_exist": scripts_exist,
            "public_url": public_url,
            "url_discovery_ok": url_ok,
            "health_check_ok": health_ok,
            "state_file_ok": state_ok,
            "state_age_seconds": state_age_seconds,
            "health_output": health_output[-500:] if health_output else "",  # Last 500 chars
        },
    )
    
    results.append(
        CaseResult(
            case_id="SMK-11",
            scope="preview_continuity",
            status="passed" if continuity_ok else "failed",
            summary=(
                f"Preview continuity verified: URL={public_url[:50]}... scripts={scripts_exist} health={health_ok}"
                if continuity_ok
                else f"Preview continuity failed: scripts_exist={scripts_exist} url_ok={url_ok} health_ok={health_ok}"
            ),
            evidence=[
                "Verified check_preview_health.sh exists and runs",
                f"Verified get_public_preview_url.sh returns valid URL: {url_ok}",
                f"Health check exit status: {'0' if health_ok else 'non-zero'}",
            ],
            artifacts=[str(artifact_path.relative_to(REPO_ROOT))],
            details={
                "public_url": public_url,
                "url_discovery_ok": url_ok,
                "health_check_ok": health_ok,
                "state_file_ok": state_ok,
                "scripts_exist": scripts_exist,
            },
        )
    )
    
    return results


def run_public_smoke(*, output_dir: Path) -> list[CaseResult]:
    passwords = load_smoke_passwords()
    user_a = SMOKE_ACCOUNT_SPECS[0]
    public_base_url = detect_public_base_url()
    if not public_base_url:
        return [
            CaseResult(
                case_id="SMK-08",
                scope="public",
                status="blocked",
                summary="No current public preview host was discoverable from env or the local ngrok inspect API.",
                evidence=[
                    "checked OPERATOR_SMOKE_PUBLIC_BASE_URL",
                    "checked http://127.0.0.1:4040/api/tunnels for localhost:3000",
                ],
            ),
            CaseResult(
                case_id="SMK-09",
                scope="public",
                status="blocked",
                summary="Authenticated public bootstrap could not run because no public preview host was discoverable.",
                evidence=["public host discovery failed before login/bootstrap"],
            ),
        ]

    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    root_status, root_headers, root_body = http_text(opener, url=public_base_url)
    root_artifact = output_dir / "SMK-08-public-root.html"
    root_artifact.write_text(root_body, encoding="utf-8")
    root_kind, root_note = classify_public_root_response(
        status_code=root_status,
        content_type=root_headers.get("Content-Type"),
        body=root_body,
    )
    root_ok = root_kind in {"provider_interstitial", "shell_gate"}

    login_status, login_payload = http_json(
        opener,
        url=f"{public_base_url}{LOGIN_ENDPOINT}",
        method="POST",
        data={
            "username": user_a.identifier,
            "password": passwords[user_a.identifier],
        },
    )
    bootstrap_status, bootstrap_payload = http_json(
        opener,
        url=f"{public_base_url}{BOOTSTRAP_ENDPOINT}",
    )
    bootstrap_artifact = output_dir / "SMK-09-public-bootstrap.json"
    save_json(
        bootstrap_artifact,
        {
            "login_status": login_status,
            "login_payload": login_payload,
            "bootstrap_status": bootstrap_status,
            "bootstrap_payload": bootstrap_payload,
        },
    )
    bootstrap_ok = (
        login_status == 200
        and isinstance(login_payload, dict)
        and login_payload.get("status") == "ok"
        and bootstrap_status == 200
        and isinstance(bootstrap_payload, dict)
        and bootstrap_payload.get("phase") == "app"
        and bootstrap_payload.get("session", {}).get("authenticated") is True
        and bootstrap_payload.get("session", {}).get("user", {}).get("identifier") == user_a.identifier
    )

    return [
        CaseResult(
            case_id="SMK-08",
            scope="public",
            status="passed" if root_ok else "failed",
            summary=(
                f"Public host reachable: {root_note}."
                if root_ok
                else f"Public host root did not meet the smoke rule: {root_note}."
            ),
            evidence=[
                f"GET {public_base_url}",
                f"classified root response as {root_kind}",
            ],
            artifacts=[str(root_artifact.relative_to(REPO_ROOT))],
            details={"public_base_url": public_base_url, "status": root_status, "classification": root_kind},
        ),
        CaseResult(
            case_id="SMK-09",
            scope="public",
            status="passed" if bootstrap_ok else "failed",
            summary=(
                "Authenticated bootstrap succeeded on the current public preview host."
                if bootstrap_ok
                else "Authenticated bootstrap failed on the current public preview host."
            ),
            evidence=[
                f"POST {public_base_url}{LOGIN_ENDPOINT}",
                f"GET {public_base_url}{BOOTSTRAP_ENDPOINT}",
            ],
            artifacts=[str(bootstrap_artifact.relative_to(REPO_ROOT))],
            details={"public_base_url": public_base_url, "login": login_payload, "bootstrap": bootstrap_payload},
        ),
    ]


def run_smoke(args: argparse.Namespace) -> int:
    if not args.skip_reset:
        asyncio.run(seed_smoke_accounts(reset_threads=True))
        reset_smoke_artifacts()
    else:
        asyncio.run(seed_smoke_accounts(reset_threads=False))

    output_dir = make_output_dir(args.output_dir)
    results: list[CaseResult] = []
    metadata = {
        "run_at": utc_now_iso(),
        "scope": args.scope,
        "local_base_url": local_base_url(),
        "public_base_url": detect_public_base_url(),
    }

    if args.scope in {"local", "all"}:
        results.extend(
            run_local_smoke(
                base_url=local_base_url(),
                output_dir=output_dir,
                headed=args.headed,
            )
        )
        # Add preview continuity check for local scope
        results.extend(run_preview_continuity_check(output_dir=output_dir))
    if args.scope in {"public", "all"}:
        results.extend(run_public_smoke(output_dir=output_dir))

    summary = {
        "metadata": metadata,
        "results": [asdict(result) for result in results],
    }
    save_json(output_dir / "results.json", summary)
    latest_path = OUTPUT_ROOT / "latest.json"
    save_json(latest_path, summary)

    failed = [result.case_id for result in results if result.status != "passed"]
    for result in results:
        print(f"{result.case_id} [{result.scope}] {result.status}: {result.summary}")
    print(f"Results: {output_dir / 'results.json'}")
    if failed:
        print("Non-passing cases: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "seed":
            actions = asyncio.run(seed_smoke_accounts(reset_threads=args.reset_threads))
            print("\n".join(actions))
            return 0
        if args.command == "reset":
            deleted = asyncio.run(reset_smoke_threads())
            artifact_count = 0 if args.keep_artifacts else reset_smoke_artifacts()
            print(f"threads_deleted={deleted}")
            print(f"artifact_entries_removed={artifact_count}")
            return 0
        if args.command == "run":
            return run_smoke(args)
    except PlaywrightTimeoutError as exc:
        print(f"Playwright timed out: {exc}", file=sys.stderr)
        return 1
    except (OSError, URLError, ValueError, asyncpg.PostgresError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        traceback.print_exc()
        return 1

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
# CI trigger: force smoke test run
