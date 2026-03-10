from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.evals.operator_eval_run_prep import prepare_operator_eval_run


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a manual or semi-manual operator-eval review bundle.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/operator_eval_runs",
        help="Root directory where the timestamped run bundle will be created.",
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Optional slugged label appended to the generated run id.",
    )
    parser.add_argument(
        "--category",
        action="append",
        help="Optional case category filter. Can be passed multiple times.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        help="Optional case_id filter. Can be passed multiple times.",
    )
    parser.add_argument(
        "--app-revision",
        default=None,
        help="Override the git-derived short SHA stored in the bundle.",
    )
    parser.add_argument(
        "--model-provider",
        default="",
        help="Optional model provider label to prefill in the scorecard.",
    )
    parser.add_argument(
        "--model-name",
        default="",
        help="Optional model name to prefill in the scorecard.",
    )
    parser.add_argument(
        "--reviewer",
        default="",
        help="Optional reviewer name to prefill in the scorecard.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    bundle = prepare_operator_eval_run(
        output_root=Path(args.output_dir),
        categories=args.category,
        case_ids=args.case_id,
        run_label=args.run_label,
        app_revision=args.app_revision,
        model_provider=args.model_provider,
        model_name=args.model_name,
        reviewer=args.reviewer,
    )
    print(json.dumps(bundle.to_summary_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
