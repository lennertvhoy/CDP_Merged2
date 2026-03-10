from __future__ import annotations

import csv
import json
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_BANK_PATH = Path("docs/evals/operator_eval_cases.v1.json")
DEFAULT_SCORECARD_TEMPLATE_PATH = Path("docs/evals/operator_eval_scorecard_template.csv")
DEFAULT_OUTPUT_ROOT = Path("output/operator_eval_runs")


class OperatorEvalRunPrepError(ValueError):
    """Raised when an operator-eval run bundle cannot be prepared."""


@dataclass(frozen=True)
class OperatorEvalRunBundle:
    """Filesystem outputs for a prepared operator-eval review run."""

    run_id: str
    output_dir: Path
    manifest_path: Path
    case_bundle_path: Path
    scorecard_path: Path
    prompt_pack_path: Path
    selected_case_ids: tuple[str, ...]

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "output_dir": str(self.output_dir),
            "manifest": str(self.manifest_path),
            "case_bundle": str(self.case_bundle_path),
            "scorecard": str(self.scorecard_path),
            "prompt_pack": str(self.prompt_pack_path),
            "selected_case_ids": list(self.selected_case_ids),
        }


def prepare_operator_eval_run(
    *,
    repo_root: Path = REPO_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    eval_bank_path: Path = DEFAULT_EVAL_BANK_PATH,
    scorecard_template_path: Path = DEFAULT_SCORECARD_TEMPLATE_PATH,
    categories: Iterable[str] | None = None,
    case_ids: Iterable[str] | None = None,
    run_label: str | None = None,
    app_revision: str | None = None,
    model_provider: str = "",
    model_name: str = "",
    reviewer: str = "",
    generated_at: datetime | None = None,
) -> OperatorEvalRunBundle:
    """Create a per-run operator-eval bundle for manual or semi-manual review."""

    resolved_repo_root = repo_root.resolve()
    resolved_eval_bank_path = _resolve_repo_path(resolved_repo_root, eval_bank_path)
    resolved_scorecard_template_path = _resolve_repo_path(
        resolved_repo_root,
        scorecard_template_path,
    )
    resolved_output_root = _resolve_repo_path(resolved_repo_root, output_root)

    eval_bank = json.loads(resolved_eval_bank_path.read_text(encoding="utf-8"))
    selected_cases = select_eval_cases(
        eval_bank,
        categories=categories,
        case_ids=case_ids,
    )

    run_timestamp = (generated_at or datetime.now(UTC)).astimezone(UTC)
    run_id = build_run_id(run_timestamp, run_label)
    run_revision = app_revision or resolve_git_revision(resolved_repo_root)
    output_dir = resolved_output_root / run_id
    _create_output_dir(output_dir)

    scorecard_header = load_scorecard_header(resolved_scorecard_template_path)
    scorecard_rows = build_scorecard_rows(
        selected_cases,
        run_id=run_id,
        run_timestamp=run_timestamp,
        app_revision=run_revision,
        model_provider=model_provider,
        model_name=model_name,
        reviewer=reviewer,
    )

    manifest_path = output_dir / "manifest.json"
    case_bundle_path = output_dir / "cases.json"
    scorecard_path = output_dir / "scorecard.csv"
    prompt_pack_path = output_dir / "prompts.md"

    case_bundle = {
        "schema_version": "operator_eval_case_bundle.v1",
        "generated_at": run_timestamp.isoformat(),
        "run_id": run_id,
        "app_revision": run_revision,
        "scoring_dimensions": eval_bank["scoring_dimensions"],
        "required_sections": eval_bank["required_sections"],
        "cases": selected_cases,
    }
    manifest = {
        "schema_version": "operator_eval_run_manifest.v1",
        "generated_at": run_timestamp.isoformat(),
        "run_id": run_id,
        "app_revision": run_revision,
        "model_provider": model_provider,
        "model_name": model_name,
        "reviewer": reviewer,
        "selected_case_count": len(selected_cases),
        "selected_case_ids": [case["case_id"] for case in selected_cases],
        "selected_categories": sorted({case["category"] for case in selected_cases}),
        "filters": {
            "categories": sorted(set(categories or [])),
            "case_ids": sorted(set(case_ids or [])),
        },
        "source_files": {
            "eval_bank": _to_repo_relative(resolved_eval_bank_path, resolved_repo_root),
            "scorecard_template": _to_repo_relative(
                resolved_scorecard_template_path,
                resolved_repo_root,
            ),
        },
        "outputs": {
            "case_bundle": case_bundle_path.name,
            "scorecard": scorecard_path.name,
            "prompt_pack": prompt_pack_path.name,
        },
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    case_bundle_path.write_text(
        json.dumps(case_bundle, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_scorecard_csv(scorecard_path, scorecard_header, scorecard_rows)
    prompt_pack_path.write_text(
        render_prompt_pack(
            selected_cases,
            run_id=run_id,
            run_timestamp=run_timestamp,
            app_revision=run_revision,
            model_provider=model_provider,
            model_name=model_name,
        ),
        encoding="utf-8",
    )

    return OperatorEvalRunBundle(
        run_id=run_id,
        output_dir=output_dir,
        manifest_path=manifest_path,
        case_bundle_path=case_bundle_path,
        scorecard_path=scorecard_path,
        prompt_pack_path=prompt_pack_path,
        selected_case_ids=tuple(case["case_id"] for case in selected_cases),
    )


def select_eval_cases(
    eval_bank: dict[str, Any],
    *,
    categories: Iterable[str] | None = None,
    case_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Select a reproducible subset of operator eval cases."""

    cases = eval_bank.get("cases")
    if not isinstance(cases, list) or not cases:
        raise OperatorEvalRunPrepError("Operator eval bank does not contain any cases.")

    selected_cases = list(cases)
    known_case_ids = {str(case["case_id"]) for case in cases}
    requested_case_ids = set(case_ids or [])
    requested_categories = set(categories or [])

    unknown_case_ids = sorted(requested_case_ids - known_case_ids)
    if unknown_case_ids:
        joined = ", ".join(unknown_case_ids)
        raise OperatorEvalRunPrepError(f"Unknown operator eval case_id values: {joined}")

    if requested_categories:
        selected_cases = [
            case for case in selected_cases if case["category"] in requested_categories
        ]
    if requested_case_ids:
        selected_cases = [case for case in selected_cases if case["case_id"] in requested_case_ids]

    if not selected_cases:
        raise OperatorEvalRunPrepError("No operator eval cases matched the requested filters.")

    return selected_cases


def build_run_id(generated_at: datetime, run_label: str | None = None) -> str:
    """Build a human-readable run id with an optional slug label."""

    timestamp = generated_at.astimezone(UTC).strftime("%Y%m%dt%H%M%Sz").lower()
    parts = ["operator-eval", timestamp]
    if run_label:
        slug = slugify(run_label)
        if slug:
            parts.append(slug)
    return "-".join(parts)


def slugify(value: str) -> str:
    """Normalize a label into a filesystem-safe slug."""

    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def resolve_git_revision(repo_root: Path) -> str:
    """Return the current short git SHA when available."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def load_scorecard_header(scorecard_template_path: Path) -> list[str]:
    """Read the canonical operator-eval scorecard header from the template."""

    with scorecard_template_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)

    if not header:
        raise OperatorEvalRunPrepError("Operator eval scorecard template is empty.")
    return header


def build_scorecard_rows(
    selected_cases: list[dict[str, Any]],
    *,
    run_id: str,
    run_timestamp: datetime,
    app_revision: str,
    model_provider: str,
    model_name: str,
    reviewer: str,
) -> list[dict[str, str]]:
    """Prefill the manual-review scorecard rows for each selected case."""

    run_date = run_timestamp.astimezone(UTC).date().isoformat()
    rows: list[dict[str, str]] = []
    for case in selected_cases:
        rows.append(
            {
                "run_id": run_id,
                "run_date": run_date,
                "app_revision": app_revision,
                "model_provider": model_provider,
                "model_name": model_name,
                "case_id": str(case["case_id"]),
                "case_version": str(case["version"]),
                "category": str(case["category"]),
                "prompt_language": str(case.get("prompt_language") or "en"),
                "intent_score": "",
                "autonomy_score": "",
                "trust_score": "",
                "actionability_score": "",
                "ux_product_polish_score": "",
                "weighted_total": "",
                "answer_first_pass": "",
                "tool_leakage_fail": "",
                "hallucinated_missing_data_fail": "",
                "copy_ux_failure": "",
                "export_ux_failure": "",
                "severity": "",
                "reviewer": reviewer,
                "notes": "",
                "recommended_fix": "",
            }
        )
    return rows


def write_scorecard_csv(
    scorecard_path: Path,
    header: list[str],
    rows: list[dict[str, str]],
) -> None:
    """Write the prefilled scorecard rows using the canonical column order."""

    with scorecard_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in header})


def render_prompt_pack(
    selected_cases: list[dict[str, Any]],
    *,
    run_id: str,
    run_timestamp: datetime,
    app_revision: str,
    model_provider: str,
    model_name: str,
) -> str:
    """Render a reviewer-friendly markdown packet of the selected prompts."""

    lines = [
        f"# Operator Eval Run `{run_id}`",
        "",
        f"- Generated at: `{run_timestamp.astimezone(UTC).isoformat()}`",
        f"- App revision: `{app_revision}`",
        f"- Model provider: `{model_provider or 'pending'}`",
        f"- Model name: `{model_name or 'pending'}`",
        f"- Selected cases: `{len(selected_cases)}`",
        "",
    ]

    for index, case in enumerate(selected_cases, start=1):
        must_fail_if = ", ".join(case["score_focus"]["must_fail_if"])
        risk_tags = ", ".join(case.get("risk_tags") or [])
        primary_dimensions = ", ".join(case["score_focus"]["primary_dimensions"])
        lines.extend(
            [
                f"## {index}. `{case['case_id']}`",
                "",
                f"- Version: `{case['version']}`",
                f"- Category: `{case['category']}`",
                f"- Source basis: `{case.get('source_basis', 'unspecified')}`",
                f"- Risk tags: `{risk_tags or 'none'}`",
                f"- Primary score focus: `{primary_dimensions}`",
                f"- Must fail if: `{must_fail_if}`",
                "",
                "```text",
                str(case["prompt"]),
                "```",
                "",
            ]
        )

    return "\n".join(lines)


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _to_repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _create_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        raise OperatorEvalRunPrepError(
            f"Operator eval output directory already exists: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=False)
