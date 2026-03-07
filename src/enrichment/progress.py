"""
Progress tracking and cost monitoring for enrichment pipeline.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EnrichmentProgress:
    """Track progress of enrichment operations."""

    # Identifiers
    job_id: str
    source: str

    # Progress
    total: int = 0
    processed: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0

    # Timing
    started_at: str | None = None
    completed_at: str | None = None
    last_update: str | None = None

    # Status
    status: str = "pending"  # pending, running, paused, completed, failed
    error_message: str | None = None

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total == 0:
            return 0.0
        return (self.processed / self.total) * 100

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.processed == 0:
            return 0.0
        return (self.success / self.processed) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            **asdict(self),
            "progress_percent": round(self.progress_percent, 2),
            "success_rate": round(self.success_rate, 2),
        }


class ProgressTracker:
    """
    Track and persist enrichment progress.

    Stores progress in JSON files for monitoring and resumption.
    """

    def __init__(self, progress_dir: str = "./data/progress"):
        self.progress_dir = Path(progress_dir)
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        self._current_jobs: dict[str, EnrichmentProgress] = {}

    def _get_progress_file(self, job_id: str) -> Path:
        """Get progress file path."""
        return self.progress_dir / f"{job_id}.json"

    def start_job(
        self,
        job_id: str,
        source: str,
        total: int,
    ) -> EnrichmentProgress:
        """
        Start tracking a new job.

        Args:
            job_id: Unique job identifier
            source: Enrichment source name
            total: Total items to process

        Returns:
            Progress object
        """
        progress = EnrichmentProgress(
            job_id=job_id,
            source=source,
            total=total,
            started_at=datetime.now(UTC).isoformat(),
            status="running",
        )

        self._current_jobs[job_id] = progress
        self._save_progress(progress)

        logger.info(f"Started job {job_id}: {source} ({total} items)")
        return progress

    def update_progress(
        self,
        job_id: str,
        processed: int | None = None,
        success: int | None = None,
        failed: int | None = None,
        skipped: int | None = None,
    ) -> EnrichmentProgress:
        """
        Update job progress.

        Args:
            job_id: Job identifier
            processed: Total processed count
            success: Success count
            failed: Failed count
            skipped: Skipped count

        Returns:
            Updated progress
        """
        if job_id not in self._current_jobs:
            # Try to load from file
            progress_file = self._get_progress_file(job_id)
            if progress_file.exists():
                with open(progress_file) as f:
                    data = json.load(f)
                    self._current_jobs[job_id] = EnrichmentProgress(**data)
            else:
                raise ValueError(f"Job {job_id} not found")

        progress = self._current_jobs[job_id]

        if processed is not None:
            progress.processed = processed
        if success is not None:
            progress.success = success
        if failed is not None:
            progress.failed = failed
        if skipped is not None:
            progress.skipped = skipped

        progress.last_update = datetime.now(UTC).isoformat()

        self._save_progress(progress)
        return progress

    def increment_progress(
        self,
        job_id: str,
        success: bool = True,
        skipped: bool = False,
    ) -> EnrichmentProgress:
        """
        Increment progress by one.

        Args:
            job_id: Job identifier
            success: Whether this item was successful
            skipped: Whether this item was skipped

        Returns:
            Updated progress
        """
        progress = self._current_jobs.get(job_id)
        if not progress:
            raise ValueError(f"Job {job_id} not found")

        progress.processed += 1

        if skipped:
            progress.skipped += 1
        elif success:
            progress.success += 1
        else:
            progress.failed += 1

        progress.last_update = datetime.now(UTC).isoformat()

        # Save every 100 updates to reduce I/O
        if progress.processed % 100 == 0:
            self._save_progress(progress)
            self._log_progress(progress)

        return progress

    def complete_job(
        self,
        job_id: str,
        error_message: str | None = None,
    ) -> EnrichmentProgress:
        """
        Mark job as completed.

        Args:
            job_id: Job identifier
            error_message: Optional error message if failed

        Returns:
            Final progress
        """
        progress = self._current_jobs.get(job_id)
        if not progress:
            raise ValueError(f"Job {job_id} not found")

        progress.completed_at = datetime.now(UTC).isoformat()

        if error_message:
            progress.status = "failed"
            progress.error_message = error_message
            logger.error(f"Job {job_id} failed: {error_message}")
        else:
            progress.status = "completed"
            logger.info(f"Job {job_id} completed: {progress.success}/{progress.total} success")

        self._save_progress(progress)
        self._log_progress(progress)

        return progress

    def _save_progress(self, progress: EnrichmentProgress):
        """Save progress to file."""
        progress_file = self._get_progress_file(progress.job_id)
        with open(progress_file, "w") as f:
            json.dump(progress.to_dict(), f, indent=2)

    def _log_progress(self, progress: EnrichmentProgress):
        """Log current progress."""
        logger.info(
            f"Job {progress.job_id} progress: {progress.progress_percent:.1f}% "
            f"({progress.processed}/{progress.total}) - "
            f"Success: {progress.success}, Failed: {progress.failed}, Skipped: {progress.skipped}"
        )

    def get_progress(self, job_id: str) -> EnrichmentProgress | None:
        """Get progress for a job."""
        if job_id in self._current_jobs:
            return self._current_jobs[job_id]

        progress_file = self._get_progress_file(job_id)
        if progress_file.exists():
            with open(progress_file) as f:
                data = json.load(f)
                return EnrichmentProgress(**data)

        return None

    def list_jobs(self) -> list[EnrichmentProgress]:
        """List all tracked jobs."""
        jobs = []
        for progress_file in self.progress_dir.glob("*.json"):
            with open(progress_file) as f:
                data = json.load(f)
                jobs.append(EnrichmentProgress(**data))
        return sorted(jobs, key=lambda j: j.started_at or "", reverse=True)

    def get_summary(self) -> dict:
        """Get summary of all jobs."""
        jobs = self.list_jobs()

        return {
            "total_jobs": len(jobs),
            "running": len([j for j in jobs if j.status == "running"]),
            "completed": len([j for j in jobs if j.status == "completed"]),
            "failed": len([j for j in jobs if j.status == "failed"]),
            "total_processed": sum(j.processed for j in jobs),
            "total_success": sum(j.success for j in jobs),
        }


@dataclass
class CostItem:
    """Single cost entry."""

    source: str
    operation: str
    cost_eur: float
    count: int = 1
    timestamp: str = ""
    details: dict | None = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


class CostTracker:
    """
    Track API costs across enrichment sources.

    Helps stay within €150/month budget.
    """

    def __init__(
        self,
        budget_eur: float = 150.0,
        cost_file: str = "./data/costs.json",
    ):
        self.budget_eur = budget_eur
        self.cost_file = Path(cost_file)
        self.cost_file.parent.mkdir(parents=True, exist_ok=True)

        self.costs: list[CostItem] = []
        self._load_costs()

    def _load_costs(self):
        """Load cost history."""
        if self.cost_file.exists():
            try:
                with open(self.cost_file) as f:
                    data = json.load(f)
                    self.costs = [CostItem(**item) for item in data.get("costs", [])]
            except Exception as e:
                logger.warning(f"Could not load costs: {e}")

    def _save_costs(self):
        """Save cost history."""
        with open(self.cost_file, "w") as f:
            json.dump(
                {
                    "budget_eur": self.budget_eur,
                    "total_spent_eur": self.get_total_spent(),
                    "remaining_eur": self.get_remaining(),
                    "costs": [asdict(c) for c in self.costs],
                },
                f,
                indent=2,
            )

    def record_cost(
        self,
        source: str,
        operation: str,
        cost_eur: float,
        count: int = 1,
        details: dict | None = None,
    ):
        """
        Record a cost.

        Args:
            source: Enrichment source
            operation: Operation type
            cost_eur: Cost in EUR
            count: Number of operations
            details: Optional details
        """
        cost_item = CostItem(
            source=source,
            operation=operation,
            cost_eur=cost_eur,
            count=count,
            details=details,
        )

        self.costs.append(cost_item)
        self._save_costs()

        logger.info(
            f"Cost recorded: {source}/{operation} = €{cost_eur:.4f} "
            f"(Total: €{self.get_total_spent():.2f})"
        )

    def get_total_spent(self, since: str | None = None) -> float:
        """
        Get total spent.

        Args:
            since: ISO timestamp to filter from

        Returns:
            Total cost in EUR
        """
        total = 0.0
        for cost in self.costs:
            if since and cost.timestamp < since:
                continue
            total += cost.cost_eur
        return total

    def get_remaining(self) -> float:
        """Get remaining budget."""
        return max(0, self.budget_eur - self.get_total_spent())

    def check_budget(self, estimated_cost: float) -> dict:
        """
        Check if estimated cost fits within budget.

        Args:
            estimated_cost: Estimated cost to add

        Returns:
            Budget check result
        """
        current = self.get_total_spent()
        projected = current + estimated_cost

        return {
            "current_spent_eur": round(current, 2),
            "budget_eur": self.budget_eur,
            "estimated_additional_eur": round(estimated_cost, 2),
            "projected_total_eur": round(projected, 2),
            "within_budget": projected <= self.budget_eur,
            "remaining_after_eur": round(self.budget_eur - projected, 2),
        }

    def get_summary(self) -> dict:
        """Get cost summary by source."""
        from collections import defaultdict
        from typing import Any

        by_source: dict[str, dict[str, Any]] = defaultdict(lambda: {"cost": 0.0, "count": 0})

        for cost in self.costs:
            by_source[cost.source]["cost"] += cost.cost_eur
            by_source[cost.source]["count"] += cost.count

        return {
            "budget_eur": self.budget_eur,
            "total_spent_eur": round(self.get_total_spent(), 2),
            "remaining_eur": round(self.get_remaining(), 2),
            "utilization_percent": round((self.get_total_spent() / self.budget_eur) * 100, 2),
            "by_source": {
                k: {"cost_eur": round(v["cost"], 2), "count": v["count"]}
                for k, v in by_source.items()
            },
        }
