#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATE = ROOT / "PROJECT_STATE.yaml"
STATUS = ROOT / "STATUS.md"
NEXT_ACTIONS = ROOT / "NEXT_ACTIONS.md"
RETIRED_ROOT_SUMMARIES = [
    ROOT / "GEMINI.md",
    ROOT / "PROJECT_STATUS_SUMMARY.md",
]


class LintFailure(Exception):
    pass


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_retired_summary_files(errors: list[str]) -> None:
    for path in RETIRED_ROOT_SUMMARIES:
        if path.exists():
            errors.append(f"{path.name} should be retired from the repo root.")


def check_duplicate_yaml_keys(errors: list[str]) -> None:
    text = read_text(PROJECT_STATE)
    key_re = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):(?:\s*(.*))?$")
    stack: list[tuple[int, set[str]]] = [(-1, set())]
    block_scalar_indent: int | None = None

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if block_scalar_indent is not None:
            if indent > block_scalar_indent:
                continue
            block_scalar_indent = None

        if stripped.startswith("- "):
            continue

        match = key_re.match(raw_line)
        if not match:
            continue

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()

        key = match.group(2)
        remainder = (match.group(3) or "").strip()
        current_keys = stack[-1][1]
        if key in current_keys:
            errors.append(f"Duplicate YAML key `{key}` at {PROJECT_STATE.name}:{lineno}.")
        else:
            current_keys.add(key)

        if not remainder or remainder in {"|", ">"}:
            stack.append((indent, set()))
            if remainder in {"|", ">"}:
                block_scalar_indent = indent


def extract_project_counts() -> dict[str, int]:
    text = read_text(PROJECT_STATE)
    patterns = {
        "total": r"^\s+total_companies:\s+(\d+)\s*$",
        "website_url": r"^\s+website_url:\s+(\d+)\s*$",
        "geo_latitude": r"^\s+geo_latitude:\s+(\d+)\s*$",
        "ai_description": r"^\s+ai_description:\s+(\d+)\s*$",
    }
    counts: dict[str, int] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.MULTILINE)
        if not match:
            raise LintFailure(f"Missing `{key}` canonical count in {PROJECT_STATE.name}.")
        counts[key] = int(match.group(1))
    return counts


def format_count(value: int) -> str:
    return f"{value:,}"


def check_summary_count_alignment(errors: list[str]) -> None:
    counts = extract_project_counts()
    expected = (
        f"total={format_count(counts['total'])}; "
        f"website_url={format_count(counts['website_url'])}; "
        f"geo_latitude={format_count(counts['geo_latitude'])}; "
        f"ai_description={format_count(counts['ai_description'])}"
    )

    for path in (STATUS, NEXT_ACTIONS):
        text = read_text(path)
        if expected not in text:
            errors.append(
                f"{path.name} is missing the canonical counts line `{expected}`."
            )


def check_status_shape(errors: list[str]) -> None:
    headings = re.findall(r"^## (.+)$", read_text(STATUS), flags=re.MULTILINE)
    expected = [
        "Current Headline",
        "Current State",
        "Top Risks",
        "Immediate Focus",
    ]
    if headings != expected:
        errors.append(
            f"{STATUS.name} headings must be exactly {expected}, found {headings}."
        )


def check_next_actions_shape(errors: list[str]) -> None:
    text = read_text(NEXT_ACTIONS)
    headings = re.findall(r"^## (.+)$", text, flags=re.MULTILINE)
    expected = ["Active", "Paused", "Recently Closed"]
    if headings != expected:
        errors.append(
            f"{NEXT_ACTIONS.name} headings must be exactly {expected}, found {headings}."
        )
        return

    marker = "## Recently Closed"
    tail = text.split(marker, 1)[1]
    recent_items = re.findall(r"^### ", tail, flags=re.MULTILINE)
    if len(recent_items) > 3:
        errors.append(
            f"{NEXT_ACTIONS.name} should keep at most 3 recently closed items, found {len(recent_items)}."
        )


def main() -> int:
    errors: list[str] = []
    check_retired_summary_files(errors)
    check_duplicate_yaml_keys(errors)
    check_status_shape(errors)
    check_next_actions_shape(errors)
    try:
        check_summary_count_alignment(errors)
    except LintFailure as exc:
        errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("doc_lint: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
