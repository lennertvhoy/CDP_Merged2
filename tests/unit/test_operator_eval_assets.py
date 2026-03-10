from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_BANK_PATH = REPO_ROOT / "docs" / "evals" / "operator_eval_cases.v1.json"
SCORECARD_TEMPLATE_PATH = REPO_ROOT / "docs" / "evals" / "operator_eval_scorecard_template.csv"


def test_operator_eval_bank_has_expected_shape() -> None:
    payload = json.loads(EVAL_BANK_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "operator_eval_bank.v1"
    assert payload["scoring_dimensions"] == [
        "intent",
        "autonomy",
        "trust",
        "actionability",
        "ux_product_polish",
    ]

    required_sections = payload["required_sections"]
    assert required_sections == [
        "role_context",
        "goal",
        "constraints",
        "workflow_expectation",
        "desired_output",
        "success_criteria",
    ]

    cases = payload["cases"]
    assert len(cases) >= 8

    seen_case_ids: set[str] = set()
    seen_categories: set[str] = set()

    for case in cases:
        case_id = case["case_id"]
        assert case_id not in seen_case_ids
        seen_case_ids.add(case_id)

        assert isinstance(case["version"], int)
        assert case["version"] >= 1

        category = case["category"]
        assert isinstance(category, str)
        assert category
        seen_categories.add(category)

        sections = case["sections"]
        for section_name in required_sections:
            assert section_name in sections
            section_value = sections[section_name]
            assert section_value

        prompt = case["prompt"]
        assert isinstance(prompt, str)
        assert len(prompt) > 200
        assert "Role/Context:" in prompt
        assert "Goal:" in prompt
        assert "Constraints:" in prompt
        assert "Workflow Expectation:" in prompt
        assert "Desired Output:" in prompt
        assert "Success Criteria:" in prompt

        score_focus = case["score_focus"]
        assert score_focus["primary_dimensions"]
        assert all(
            dimension in payload["scoring_dimensions"]
            for dimension in score_focus["primary_dimensions"]
        )
        assert score_focus["must_fail_if"]

    assert "segment_search" in seen_categories
    assert "account_360" in seen_categories
    assert "export_ux" in seen_categories
    assert "copy_ux" in seen_categories
    assert "publication_parsing" in seen_categories


def test_operator_eval_scorecard_template_has_required_columns() -> None:
    with SCORECARD_TEMPLATE_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)

    assert header == [
        "run_id",
        "run_date",
        "app_revision",
        "model_provider",
        "model_name",
        "case_id",
        "case_version",
        "category",
        "prompt_language",
        "intent_score",
        "autonomy_score",
        "trust_score",
        "actionability_score",
        "ux_product_polish_score",
        "weighted_total",
        "answer_first_pass",
        "tool_leakage_fail",
        "hallucinated_missing_data_fail",
        "copy_ux_failure",
        "export_ux_failure",
        "severity",
        "reviewer",
        "notes",
        "recommended_fix",
    ]
