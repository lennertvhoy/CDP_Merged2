from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.evals.operator_eval_run_prep import (
    REPO_ROOT,
    OperatorEvalRunPrepError,
    prepare_operator_eval_run,
)


def test_prepare_operator_eval_run_writes_expected_bundle(tmp_path: Path) -> None:
    bundle = prepare_operator_eval_run(
        repo_root=REPO_ROOT,
        output_root=tmp_path,
        app_revision="946ccf4",
        model_provider="openai",
        model_name="gpt-5",
        reviewer="agent",
        case_ids=["copy_troubleshooting_clipboarditem_not_defined"],
        generated_at=datetime(2026, 3, 9, 11, 12, 13, tzinfo=UTC),
    )

    assert bundle.run_id == "operator-eval-20260309t111213z"
    assert bundle.selected_case_ids == ("copy_troubleshooting_clipboarditem_not_defined",)

    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "operator_eval_run_manifest.v1"
    assert manifest["selected_case_count"] == 1
    assert manifest["selected_case_ids"] == ["copy_troubleshooting_clipboarditem_not_defined"]
    assert manifest["filters"]["case_ids"] == ["copy_troubleshooting_clipboarditem_not_defined"]
    assert manifest["app_revision"] == "946ccf4"
    assert manifest["outputs"]["scorecard"] == "scorecard.csv"

    case_bundle = json.loads(bundle.case_bundle_path.read_text(encoding="utf-8"))
    assert case_bundle["schema_version"] == "operator_eval_case_bundle.v1"
    assert case_bundle["cases"][0]["case_id"] == "copy_troubleshooting_clipboarditem_not_defined"
    assert case_bundle["cases"][0]["category"] == "copy_ux"

    with bundle.scorecard_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == bundle.run_id
    assert row["run_date"] == "2026-03-09"
    assert row["app_revision"] == "946ccf4"
    assert row["model_provider"] == "openai"
    assert row["model_name"] == "gpt-5"
    assert row["case_id"] == "copy_troubleshooting_clipboarditem_not_defined"
    assert row["category"] == "copy_ux"
    assert row["prompt_language"] == "en"
    assert row["reviewer"] == "agent"
    assert row["intent_score"] == ""
    assert row["tool_leakage_fail"] == ""

    prompt_pack = bundle.prompt_pack_path.read_text(encoding="utf-8")
    assert "# Operator Eval Run" in prompt_pack
    assert "ClipboardItem is not defined" in prompt_pack
    assert "Must fail if" in prompt_pack


def test_prepare_operator_eval_run_filters_by_category(tmp_path: Path) -> None:
    bundle = prepare_operator_eval_run(
        repo_root=REPO_ROOT,
        output_root=tmp_path,
        app_revision="946ccf4",
        categories=["account_360"],
        generated_at=datetime(2026, 3, 9, 11, 12, 13, tzinfo=UTC),
    )

    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    assert manifest["selected_case_count"] == 2
    assert manifest["selected_categories"] == ["account_360"]


def test_prepare_operator_eval_run_rejects_unknown_case_ids(tmp_path: Path) -> None:
    with pytest.raises(
        OperatorEvalRunPrepError,
        match="Unknown operator eval case_id values: does_not_exist",
    ):
        prepare_operator_eval_run(
            repo_root=REPO_ROOT,
            output_root=tmp_path,
            case_ids=["does_not_exist"],
            generated_at=datetime(2026, 3, 9, 11, 12, 13, tzinfo=UTC),
        )
