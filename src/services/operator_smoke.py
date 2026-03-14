"""Shared helpers for the first operator-shell smoke baseline."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen

DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:3000"
DEFAULT_NGROK_INSPECT_URL = "http://127.0.0.1:4040/api/tunnels"
DEFAULT_READY_PROMPT = "Respond with the single word READY."
DEFAULT_COUNT_PROMPT = "How many companies are in Brussels?"
PUBLIC_BASE_URL_ENV = "OPERATOR_SMOKE_PUBLIC_BASE_URL"
LOCAL_BASE_URL_ENV = "OPERATOR_SMOKE_LOCAL_BASE_URL"
READY_PROMPT_ENV = "OPERATOR_SMOKE_READY_PROMPT"
COUNT_PROMPT_ENV = "OPERATOR_SMOKE_COUNT_PROMPT"

RAW_TOOL_LEAKAGE_MARKERS = (
    "tool_calls",
    "search_profiles",
    "create_segment",
    "export_segment_to_csv",
    "get_segment_stats",
    "query_unified_360",
    "assistant_message",
    "function_call",
)


@dataclass(frozen=True)
class SmokeAccountSpec:
    key: str
    identifier: str
    display_name: str
    password_env_var: str


SMOKE_ACCOUNT_SPECS: tuple[SmokeAccountSpec, ...] = (
    SmokeAccountSpec(
        key="a",
        identifier="operator-smoke-a",
        display_name="Operator Smoke A",
        password_env_var="OPERATOR_SMOKE_A_PASSWORD",
    ),
    SmokeAccountSpec(
        key="b",
        identifier="operator-smoke-b",
        display_name="Operator Smoke B",
        password_env_var="OPERATOR_SMOKE_B_PASSWORD",
    ),
)


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def local_base_url(environ: Mapping[str, str] | None = None) -> str:
    env = environ or os.environ
    return normalize_base_url(env.get(LOCAL_BASE_URL_ENV, DEFAULT_LOCAL_BASE_URL))


def ready_prompt(environ: Mapping[str, str] | None = None) -> str:
    env = environ or os.environ
    return env.get(READY_PROMPT_ENV, DEFAULT_READY_PROMPT).strip() or DEFAULT_READY_PROMPT


def count_prompt(environ: Mapping[str, str] | None = None) -> str:
    env = environ or os.environ
    return env.get(COUNT_PROMPT_ENV, DEFAULT_COUNT_PROMPT).strip() or DEFAULT_COUNT_PROMPT


def load_smoke_passwords(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    env = environ or os.environ
    passwords: dict[str, str] = {}
    missing: list[str] = []

    for spec in SMOKE_ACCOUNT_SPECS:
        password = (env.get(spec.password_env_var) or "").strip()
        if not password:
            missing.append(spec.password_env_var)
            continue
        passwords[spec.identifier] = password

    if missing:
        raise ValueError("Missing smoke-account password env vars: " + ", ".join(sorted(missing)))

    return passwords


def detect_public_base_url(
    environ: Mapping[str, str] | None = None,
    *,
    inspect_api_url: str = DEFAULT_NGROK_INSPECT_URL,
) -> str | None:
    env = environ or os.environ
    explicit = (env.get(PUBLIC_BASE_URL_ENV) or "").strip()
    if explicit:
        return normalize_base_url(explicit)

    try:
        with urlopen(inspect_api_url, timeout=5) as response:
            payload = json.load(response)
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return None

    tunnels = payload.get("tunnels")
    if not isinstance(tunnels, list):
        return None

    for tunnel in tunnels:
        if not isinstance(tunnel, dict):
            continue
        config = tunnel.get("config")
        if not isinstance(config, dict):
            continue
        if config.get("addr") == "http://localhost:3000":
            public_url = tunnel.get("public_url")
            if isinstance(public_url, str) and public_url.strip():
                return normalize_base_url(public_url)

    return None


def classify_public_root_response(
    *,
    status_code: int,
    content_type: str | None,
    body: str,
) -> tuple[str, str]:
    normalized_body = body.lower()
    normalized_type = (content_type or "").lower()

    if "err_ngrok_6024" in normalized_body or (
        "ngrok" in normalized_body and "before you visit" in normalized_body
    ):
        return ("provider_interstitial", "ngrok free-tier warning interstitial is expected")

    if "private access" in normalized_body or "loading private preview" in normalized_body:
        return ("shell_gate", "shell gate is reachable on the public host")

    if "cdp_merged private preview" in normalized_body:
        return ("shell_gate", "shell root responded with the operator-shell preview page")

    if 200 <= status_code < 400 and "text/html" in normalized_type:
        return ("unexpected_html", "public host returned HTML but not the expected shell gate")

    return ("unexpected", f"public host returned status={status_code}")


def detect_tool_leakage(text: str) -> list[str]:
    normalized = text.lower()
    return [marker for marker in RAW_TOOL_LEAKAGE_MARKERS if marker in normalized]


def first_meaningful_line(text: str) -> str:
    for line in text.replace("\r\n", "\n").split("\n"):
        normalized = line.strip()
        if normalized:
            return normalized
    return ""


def looks_like_answer_first_count_reply(text: str) -> bool:
    first_line = first_meaningful_line(text)
    if not first_line:
        return False
    return bool(re.search(r"\d", first_line))
