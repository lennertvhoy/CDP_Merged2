"""
LLM Spend Guard - App-side hard stop for monthly LLM budget.

Prevents overspend by tracking estimated costs and disabling LLM calls
when the budget threshold is reached.

Based on the CostTracker pattern from enrichment/progress.py.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMCostEntry:
    """Single LLM API call cost entry."""

    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_eur: float
    request_type: str  # "routing" | "final_answer" | "other"


class LLMSpendGuard:
    """
    App-side hard stop for LLM spending.

    Tracks per-request costs and disables LLM calls when budget is exceeded.
    OpenAI project budgets are soft alerts only - this provides the hard stop.
    """

    def __init__(
        self,
        budget_eur: float | None = None,
        hard_stop_eur: float | None = None,
        cost_file: str | None = None,
    ):
        """
        Initialize the spend guard.

        Args:
            budget_eur: Monthly budget in EUR (default from settings)
            hard_stop_eur: Hard stop threshold in EUR (default from settings)
            cost_file: File to persist cost data (default from settings)
        """
        self.budget_eur = budget_eur or settings.LLM_MONTHLY_BUDGET_EUR
        self.hard_stop_eur = hard_stop_eur or settings.LLM_BUDGET_HARD_STOP_EUR
        self.cost_file = Path(cost_file or settings.LLM_COST_TRACKING_FILE)
        self.cost_file.parent.mkdir(parents=True, exist_ok=True)

        # Pricing (per 1M tokens) - gpt-4.1-mini default
        self.input_price_per_1m = settings.OPENAI_INPUT_PRICE_PER_1M
        self.output_price_per_1m = settings.OPENAI_OUTPUT_PRICE_PER_1M

        self.costs: list[LLMCostEntry] = []
        self._load_costs()

        logger.info(
            "LLMSpendGuard initialized",
            budget_eur=self.budget_eur,
            hard_stop_eur=self.hard_stop_eur,
            cost_file=str(self.cost_file),
        )

    def _load_costs(self) -> None:
        """Load cost history from file."""
        if not self.cost_file.exists():
            return

        try:
            with open(self.cost_file) as f:
                data = json.load(f)
                # Filter to current month only
                current_month = datetime.now(timezone.utc).strftime("%Y-%m")
                self.costs = [
                    LLMCostEntry(**item)
                    for item in data.get("costs", [])
                    if item.get("timestamp", "").startswith(current_month)
                ]
                logger.info(
                    "Loaded LLM cost history",
                    entries_loaded=len(self.costs),
                    month=current_month,
                )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Could not load LLM costs: {e}")
            self.costs = []

    def _save_costs(self) -> None:
        """Save cost history to file."""
        try:
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            # Keep only current month costs (archiving not needed for this use case)
            data = {
                "month": current_month,
                "budget_eur": self.budget_eur,
                "hard_stop_eur": self.hard_stop_eur,
                "costs": [asdict(c) for c in self.costs],
            }
            with open(self.cost_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save LLM costs: {e}")

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for a request.

        Args:
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens

        Returns:
            Estimated cost in EUR
        """
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_1m
        return input_cost + output_cost

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        request_type: str = "other",
    ) -> dict[str, Any]:
        """
        Record actual usage from an LLM response.

        Args:
            model: Model name used
            input_tokens: Actual input tokens used
            output_tokens: Actual output tokens used
            request_type: Type of request (routing, final_answer, other)

        Returns:
            Summary of the recorded entry
        """
        cost = self.estimate_cost(input_tokens, output_tokens)
        entry = LLMCostEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_eur=cost,
            request_type=request_type,
        )
        self.costs.append(entry)
        self._save_costs()

        total = self.get_monthly_total()
        remaining = max(0, self.hard_stop_eur - total)

        logger.info(
            "LLM usage recorded",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_eur=round(cost, 6),
            total_monthly_eur=round(total, 4),
            remaining_eur=round(remaining, 4),
            request_type=request_type,
        )

        return {
            "cost_eur": round(cost, 6),
            "total_monthly_eur": round(total, 4),
            "remaining_eur": round(remaining, 4),
            "hard_stop_reached": total >= self.hard_stop_eur,
        }

    def get_monthly_total(self) -> float:
        """Get total spent this month."""
        return sum(c.estimated_cost_eur for c in self.costs)

    def get_summary(self) -> dict[str, Any]:
        """Get cost summary."""
        total = self.get_monthly_total()
        remaining = max(0, self.hard_stop_eur - total)
        utilization = (total / self.hard_stop_eur * 100) if self.hard_stop_eur > 0 else 0

        # Count by request type
        by_type: dict[str, dict[str, Any]] = {}
        for cost in self.costs:
            rt = cost.request_type
            if rt not in by_type:
                by_type[rt] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_eur": 0.0}
            by_type[rt]["calls"] += 1
            by_type[rt]["input_tokens"] += cost.input_tokens
            by_type[rt]["output_tokens"] += cost.output_tokens
            by_type[rt]["cost_eur"] += cost.estimated_cost_eur

        return {
            "budget_eur": self.budget_eur,
            "hard_stop_eur": self.hard_stop_eur,
            "spent_eur": round(total, 4),
            "remaining_eur": round(remaining, 4),
            "utilization_percent": round(utilization, 2),
            "total_calls": len(self.costs),
            "by_request_type": {
                k: {
                    "calls": v["calls"],
                    "input_tokens": v["input_tokens"],
                    "output_tokens": v["output_tokens"],
                    "cost_eur": round(v["cost_eur"], 4),
                }
                for k, v in by_type.items()
            },
        }

    def check_budget(self, estimated_input_tokens: int = 0, estimated_output_tokens: int = 0) -> dict[str, Any]:
        """
        Check if a request would exceed budget.

        Args:
            estimated_input_tokens: Estimated input tokens for the request
            estimated_output_tokens: Estimated output tokens for the request

        Returns:
            Budget check result with 'allowed' boolean
        """
        current = self.get_monthly_total()
        estimated_cost = self.estimate_cost(estimated_input_tokens, estimated_output_tokens)
        projected = current + estimated_cost

        allowed = projected < self.hard_stop_eur

        return {
            "allowed": allowed,
            "current_spent_eur": round(current, 4),
            "estimated_cost_eur": round(estimated_cost, 6),
            "projected_total_eur": round(projected, 4),
            "hard_stop_eur": self.hard_stop_eur,
            "remaining_before_hard_stop_eur": round(max(0, self.hard_stop_eur - current), 4),
            "message": (
                None
                if allowed
                else f"🛑 Monthly LLM budget reached ({self.hard_stop_eur} EUR). Please try again next month."
            ),
        }

    def can_make_request(self) -> bool:
        """Quick check if any requests are allowed."""
        return self.get_monthly_total() < self.hard_stop_eur


# Global instance for singleton-like access
_spend_guard: LLMSpendGuard | None = None


def get_spend_guard() -> LLMSpendGuard:
    """Get or create the global spend guard instance."""
    global _spend_guard
    if _spend_guard is None:
        _spend_guard = LLMSpendGuard()
    return _spend_guard


def reset_spend_guard() -> None:
    """Reset the global spend guard (mainly for testing)."""
    global _spend_guard
    _spend_guard = None
