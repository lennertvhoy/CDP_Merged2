#!/usr/bin/env python3
"""
Enrichment Progress Dashboard - Real-time monitoring for the enrichment pipeline.

Shows:
- Database-level progress (pending/enriched counts)
- Log-parsed chunk progress and rates (COMBINED from all log files)
- Estimated time remaining
- Recent errors and enrichment quality metrics
- Data integrity warnings per AGENTS.md compliance

Usage:
    export DATABASE_URL="postgresql://user:pass@host:5432/db?sslmode=require"
    python scripts/enrich_dashboard.py

    # Watch mode (updates every 30 seconds)
    python scripts/enrich_dashboard.py --watch

    # Parse specific log file
    python scripts/enrich_dashboard.py --log logs/enrichment/cbe_continuous_20260303_185929.log
"""

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Optional asyncpg import - dashboard works without DB for log-only mode
try:
    import asyncpg
    HAS_DB = True
except ImportError:
    HAS_DB = False

LOG_DIR = Path("logs/enrichment")
TOTAL_COMPANIES = 1_940_603  # From KBO import


def get_database_url() -> str | None:
    """Get database URL from environment."""
    if database_url := os.environ.get("DATABASE_URL"):
        return database_url

    host = os.environ.get("DB_HOST")
    name = os.environ.get("DB_NAME")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")
    port = os.environ.get("DB_PORT", "5432")

    if all([host, name, user, password]):
        return f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode=require"

    return None


async def get_db_stats() -> dict[str, Any] | None:
    """Get enrichment stats from database."""
    if not HAS_DB:
        return None

    db_url = get_database_url()
    if not db_url:
        return None

    try:
        conn = await asyncpg.connect(db_url)

        total = await conn.fetchval("SELECT COUNT(*) FROM companies")
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM companies WHERE sync_status = 'pending'"
        )
        enriched = await conn.fetchval(
            "SELECT COUNT(*) FROM companies WHERE sync_status = 'enriched'"
        )
        error = await conn.fetchval(
            "SELECT COUNT(*) FROM companies WHERE sync_status = 'error'"
        )

        await conn.close()

        return {
            "total": total,
            "pending": pending,
            "enriched": enriched,
            "error": error,
            "progress_pct": (enriched / total * 100) if total > 0 else 0,
        }
    except Exception as e:
        return {"error": str(e)}


def parse_continuous_log(content: str) -> dict[str, Any]:
    """Parse continuous enrichment log format (chunk-based)."""
    chunk_completes = len(re.findall(r"ENRICHMENT COMPLETE", content))

    # Parse enrichment results from log
    enriched_pattern = r"Enriched:\s+(\d+)"
    skipped_pattern = r"Skipped:\s+(\d+)"
    failed_pattern = r"Failed:\s+(\d+)"
    errors_pattern = r"Errors:\s+(\d+)"

    enriched_counts = [int(x) for x in re.findall(enriched_pattern, content)]
    skipped_counts = [int(x) for x in re.findall(skipped_pattern, content)]
    failed_counts = [int(x) for x in re.findall(failed_pattern, content)]
    errors_counts = [int(x) for x in re.findall(errors_pattern, content)]

    # Parse timestamps to calculate rate
    chunk_times = re.findall(
        r"Chunk (\d+) completed at \w+\s+(\d{2}\s+\w+\s+\d{4}\s+\d{2}:\d{2}:\d{2})",
        content
    )

    rate_per_hour = None
    avg_chunk_time = None

    if len(chunk_times) >= 2:
        try:
            month_map = {
                "jan": "Jan", "feb": "Feb", "mrt": "Mar", "apr": "Apr",
                "mei": "May", "jun": "Jun", "jul": "Jul", "aug": "Aug",
                "sep": "Sep", "okt": "Oct", "nov": "Nov", "dec": "Dec"
            }

            def parse_dutch_date(date_str: str) -> datetime:
                for dutch, english in month_map.items():
                    date_str = date_str.lower().replace(dutch, english)
                return datetime.strptime(date_str.strip(), "%d %b %Y %H:%M:%S")

            first_chunk_time = parse_dutch_date(chunk_times[0][1])
            last_chunk_time = parse_dutch_date(chunk_times[-1][1])

            elapsed_hours = (last_chunk_time - first_chunk_time).total_seconds() / 3600
            chunks_done = int(chunk_times[-1][0]) - int(chunk_times[0][0]) + 1

            if elapsed_hours > 0:
                rate_per_hour = (chunks_done * 1000) / elapsed_hours
                avg_chunk_time = (elapsed_hours * 3600) / chunks_done
        except (ValueError, IndexError):
            pass

    # Recent errors
    error_lines = []
    for line in content.split("\n"):
        if "error" in line.lower() or "failed" in line.lower():
            error_lines.append(line.strip())

    return {
        "chunks_completed": chunk_completes,
        "total_enriched": sum(enriched_counts),
        "total_skipped": sum(skipped_counts),
        "total_failed": sum(failed_counts),
        "total_errors": sum(errors_counts),
        "avg_enriched_per_chunk": sum(enriched_counts) / len(enriched_counts) if enriched_counts else 0,
        "success_rate": (
            sum(enriched_counts) / (sum(enriched_counts) + sum(failed_counts)) * 100
            if (sum(enriched_counts) + sum(failed_counts)) > 0 else 0
        ),
        "rate_per_hour": rate_per_hour,
        "avg_chunk_time_seconds": avg_chunk_time,
        "recent_errors": error_lines,
    }


def parse_phase_log(content: str) -> dict[str, Any]:
    """Parse phase enrichment log format (progress-based, no chunks)."""
    # Parse progress lines: "Progress: 2,000 processed | Enriched: 1,269 | Skipped: 731 | Failed: 0"
    progress_pattern = r"Progress:\s+([\d,]+)\s+processed\s+\|\s+Enriched:\s+([\d,]+)\s+\|\s+Skipped:\s+([\d,]+)\s+\|\s+Failed:\s+(\d+)"

    progress_matches = re.findall(progress_pattern, content)

    if not progress_matches:
        return {"error": "No progress data found"}

    # Get the last progress entry for totals
    last_match = progress_matches[-1]
    total_processed = int(last_match[0].replace(",", ""))
    total_enriched = int(last_match[1].replace(",", ""))
    total_skipped = int(last_match[2].replace(",", ""))
    total_failed = int(last_match[3])

    # Calculate rate from first and last progress entries
    # Parse timestamps
    timestamp_pattern = r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
    timestamps = re.findall(timestamp_pattern, content, re.MULTILINE)

    rate_per_hour = None
    if len(timestamps) >= 2:
        try:
            first_time = datetime.strptime(timestamps[0], "%Y-%m-%d %H:%M:%S")
            last_time = datetime.strptime(timestamps[-1], "%Y-%m-%d %H:%M:%S")
            elapsed_hours = (last_time - first_time).total_seconds() / 3600

            if elapsed_hours > 0:
                rate_per_hour = total_processed / elapsed_hours
        except ValueError:
            pass

    # Recent errors
    error_lines = []
    for line in content.split("\n"):
        if "error" in line.lower() or "failed" in line.lower() or "warning" in line.lower():
            error_lines.append(line.strip())

    # For phase logs, we approximate chunks as total_processed / 1000
    # since phase logs don't have explicit chunk boundaries
    approx_chunks = total_processed // 1000

    return {
        "chunks_completed": approx_chunks,
        "total_enriched": total_enriched,
        "total_skipped": total_skipped,
        "total_failed": total_failed,
        "total_errors": 0,  # Not tracked separately in phase logs
        "avg_enriched_per_chunk": total_enriched / approx_chunks if approx_chunks > 0 else 0,
        "success_rate": (
            total_enriched / (total_enriched + total_failed) * 100
            if (total_enriched + total_failed) > 0 else 0
        ),
        "rate_per_hour": rate_per_hour,
        "avg_chunk_time_seconds": None,  # Not applicable for phase logs
        "recent_errors": error_lines,
        "total_processed": total_processed,  # Additional field for phase logs
    }


def parse_log_file(log_path: Path) -> dict[str, Any]:
    """Parse enrichment log file for progress metrics.

    Automatically detects log format (continuous vs phase) and parses accordingly.
    """
    if not log_path.exists():
        return {"error": f"Log file not found: {log_path}"}

    content = log_path.read_text()

    # Detect log format
    # Continuous logs have "Chunk X starting" and "ENRICHMENT COMPLETE"
    # Phase logs have "Progress: X processed"
    if "Chunk " in content and "ENRICHMENT COMPLETE" in content:
        return parse_continuous_log(content)
    elif "Progress:" in content and "processed" in content:
        return parse_phase_log(content)
    else:
        # Try continuous format first, then fall back
        return parse_continuous_log(content)


def find_all_logs() -> dict[str, Path | None]:
    """Find all relevant enrichment log files.

    Returns dict with 'phase' and 'continuous' log paths (may be None).
    For phase logs, picks the one with the most actual data (not just newest).
    """
    if not LOG_DIR.exists():
        return {"phase": None, "continuous": None}

    log_files = list(LOG_DIR.glob("*.log"))
    if not log_files:
        return {"phase": None, "continuous": None}

    result = {"phase": None, "continuous": None, "geocoding": None}

    # Find continuous logs (actively being written) - use most recent
    # Include both 'continuous' and 'running' log naming patterns
    continuous_logs = [p for p in log_files if "continuous" in p.name or "running" in p.name]
    if continuous_logs:
        result["continuous"] = sorted(continuous_logs, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    # Find geocoding logs separately
    geocoding_logs = [p for p in log_files if "geocoding" in p.name]
    if geocoding_logs:
        result["geocoding"] = sorted(geocoding_logs, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    # Find phase logs - pick the one with most ACTUAL DATA, not just newest
    phase_logs = [p for p in log_files if "phase" in p.name]
    if phase_logs:
        # Parse each phase log to find which has the most progress
        best_log = None
        best_count = 0

        for log_path in phase_logs:
            try:
                content = log_path.read_text()
                # Check for progress pattern
                progress_matches = re.findall(r"Progress:\s+([\d,]+)\s+processed", content)
                if progress_matches:
                    # Get the last progress number
                    last_count = int(progress_matches[-1].replace(",", ""))
                    if last_count > best_count:
                        best_count = last_count
                        best_log = log_path
                else:
                    # No progress yet - check if it's a new empty log
                    # Prefer logs with actual data over empty ones
                    if best_log is None:
                        best_log = log_path
            except Exception:
                continue

        result["phase"] = best_log

    return result


def aggregate_log_stats(log_stats: dict[str, dict]) -> dict[str, Any]:
    """Aggregate stats from multiple log files.

    Combines phase and continuous log data into unified metrics.
    Geocoding is tracked separately (it's additive enrichment, not company processing).
    """
    phase_stats = log_stats.get("phase", {})
    continuous_stats = log_stats.get("continuous", {})
    geocoding_stats = log_stats.get("geocoding", {})

    # Handle errors
    phase_error = phase_stats.get("error") if phase_stats else None
    continuous_error = continuous_stats.get("error") if continuous_stats else None
    geocoding_error = geocoding_stats.get("error") if geocoding_stats else None

    # Calculate combined totals (phase + continuous = company processing)
    phase_processed = phase_stats.get("total_processed", 0) if phase_stats else 0
    if phase_processed == 0 and phase_stats:
        # Fallback: estimate from chunks
        phase_processed = phase_stats.get("chunks_completed", 0) * 1000

    continuous_processed = continuous_stats.get("chunks_completed", 0) * 1000 if continuous_stats else 0

    total_processed = phase_processed + continuous_processed

    phase_enriched = phase_stats.get("total_enriched", 0) if phase_stats else 0
    continuous_enriched = continuous_stats.get("total_enriched", 0) if continuous_stats else 0
    total_enriched = phase_enriched + continuous_enriched

    phase_skipped = phase_stats.get("total_skipped", 0) if phase_stats else 0
    continuous_skipped = continuous_stats.get("total_skipped", 0) if continuous_stats else 0
    total_skipped = phase_skipped + continuous_skipped

    phase_failed = phase_stats.get("total_failed", 0) if phase_stats else 0
    continuous_failed = continuous_stats.get("total_failed", 0) if continuous_stats else 0
    total_failed = phase_failed + continuous_failed

    # Combine recent errors
    all_errors = []
    if phase_stats and phase_stats.get("recent_errors"):
        all_errors.extend(phase_stats["recent_errors"][-3:])
    if continuous_stats and continuous_stats.get("recent_errors"):
        all_errors.extend(continuous_stats["recent_errors"][-3:])
    if geocoding_stats and geocoding_stats.get("recent_errors"):
        all_errors.extend(geocoding_stats["recent_errors"][-3:])

    # Use continuous rate if available, otherwise phase rate
    rate_per_hour = None
    if continuous_stats and continuous_stats.get("rate_per_hour"):
        rate_per_hour = continuous_stats["rate_per_hour"]
    elif phase_stats and phase_stats.get("rate_per_hour"):
        rate_per_hour = phase_stats["rate_per_hour"]

    # Calculate combined progress percentage
    progress_pct = (total_processed / TOTAL_COMPANIES) * 100 if TOTAL_COMPANIES > 0 else 0

    # Calculate success rate
    total_attempts = total_enriched + total_failed
    success_rate = (total_enriched / total_attempts * 100) if total_attempts > 0 else 0

    return {
        "total_processed": total_processed,
        "total_enriched": total_enriched,
        "total_skipped": total_skipped,
        "total_failed": total_failed,
        "progress_pct": progress_pct,
        "success_rate": success_rate,
        "rate_per_hour": rate_per_hour,
        "recent_errors": all_errors[-5:] if all_errors else [],
        "phase_stats": phase_stats if not phase_error else None,
        "continuous_stats": continuous_stats if not continuous_error else None,
        "geocoding_stats": geocoding_stats if not geocoding_error else None,
        "phase_error": phase_error,
        "continuous_error": continuous_error,
        "geocoding_error": geocoding_error,
    }


def check_log_freshness(log_path: Path | None) -> dict[str, Any]:
    """Check if log file is fresh or stale.

    Returns dict with freshness status and warnings.
    AGENTS.md: Enrichment stats older than 2 hours require re-verification.
    """
    if not log_path or not log_path.exists():
        return {
            "exists": False,
            "mtime": None,
            "age_hours": None,
            "is_fresh": False,
            "is_stale": True,
            "warning": "Log file not found",
        }

    stat = log_path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime)
    age = datetime.now() - mtime
    age_hours = age.total_seconds() / 3600

    status = {
        "exists": True,
        "mtime": mtime,
        "age_hours": age_hours,
        "is_fresh": age_hours < 2,
        "is_stale": age_hours >= 2,
        "is_very_stale": age_hours >= 48,  # AGENTS.md: downgrade to 'reported'
        "warning": None,
    }

    if age_hours >= 48:
        status["warning"] = f"[STALE - VERIFY BEFORE USE] Log unchanged for {age_hours:.1f}h"
    elif age_hours >= 2:
        status["warning"] = f"[STALE] Log not updated for {age_hours:.1f}h - process may be stuck"

    return status


def check_process_health() -> dict[str, Any]:
    """Check if enrichment processes are actually running and making progress.

    Per AGENTS.md: Process aliveness ≠ Progress. Check log timestamps too.
    """
    import subprocess

    result = {
        "enrich_processes": [],
        "warnings": [],
        "has_active_process": False,
    }

    try:
        ps_output = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        for line in ps_output.stdout.split("\n"):
            if "enrich" in line.lower() and "python" in line.lower() and "grep" not in line.lower():
                result["enrich_processes"].append(line.strip())
                if "Sl" in line or "Rl" in line:
                    result["has_active_process"] = True

        sleeping = [p for p in result["enrich_processes"] if " S" in p or "Sl" in p]
        if sleeping and len(sleeping) == len(result["enrich_processes"]):
            result["warnings"].append(
                "All enrichment processes in S (sleeping) state - may be stuck"
            )

    except Exception as e:
        result["warnings"].append(f"Could not check process health: {e}")

    return result


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    elif seconds < 86400:
        return f"{seconds/3600:.1f}h"
    else:
        return f"{seconds/86400:.1f}d"


def print_dashboard(
    db_stats: dict | None,
    combined_stats: dict,
    log_freshness: dict[str, dict],
    process_health: dict[str, Any],
    args: argparse.Namespace
) -> None:
    """Print the enrichment dashboard."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*70}")
    print(f" ENRICHMENT PROGRESS DASHBOARD - {now}")
    print(f"{'='*70}")

    # Data Integrity Warnings (AGENTS.md compliance)
    warnings = []

    # Check log freshness for both logs
    for log_name, freshness in log_freshness.items():
        if freshness.get("warning"):
            warnings.append(f"{log_name}: {freshness['warning']}")

    warnings.extend(process_health.get("warnings", []))

    # Check for phase log stopped (critical for combined progress)
    phase_freshness = log_freshness.get("phase", {})

    if phase_freshness.get("is_stale") and not phase_freshness.get("is_very_stale"):
        warnings.append("Phase log stopped - only continuous log is active")
    elif phase_freshness.get("is_very_stale"):
        warnings.append("Phase log VERY STALE - data may be incomplete")

    if warnings:
        print("\n🚨 DATA INTEGRITY WARNINGS")
        print("-" * 40)
        for warning in warnings:
            print(f"  ⚠️  {warning}")
        print("  💡 Run with --verify for full AGENTS.md compliance check")

    # Combined Progress Section (NEW - shows TRUE progress)
    print("\n📊 COMBINED ENRICHMENT PROGRESS (ALL LOGS)")
    print("-" * 40)

    total_processed = combined_stats["total_processed"]
    progress_pct = combined_stats["progress_pct"]

    # Progress bar
    bar_width = 30
    filled = int(bar_width * progress_pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)

    print(f"  Total processed:     {total_processed:,}")
    print(f"  Total companies:     {TOTAL_COMPANIES:,}")
    print(f"  Progress:            [{bar}] {progress_pct:.2f}%")
    print(f"  Total enriched:      {combined_stats['total_enriched']:,}")
    print(f"  Total skipped:       {combined_stats['total_skipped']:,}")
    print(f"  Total failed:        {combined_stats['total_failed']:,}")
    print(f"  Success rate:        {combined_stats['success_rate']:.1f}%")

    if combined_stats["rate_per_hour"]:
        remaining = TOTAL_COMPANIES - total_processed
        hours_left = remaining / combined_stats["rate_per_hour"]

        print("\n⏱️  RATE & ESTIMATE")
        print("-" * 40)
        print(f"  Processing rate:     {combined_stats['rate_per_hour']:,.0f} companies/hour")
        print(f"  Remaining:           {remaining:,} companies")
        print(f"  Est. time left:      {format_duration(hours_left * 3600)}")

    # Individual Log Stats Section
    print("\n📝 INDIVIDUAL LOG STATUS")
    print("-" * 40)

    phase_stats = combined_stats.get("phase_stats")
    continuous_stats = combined_stats.get("continuous_stats")

    if phase_stats:
        phase_processed = phase_stats.get("total_processed", phase_stats.get("chunks_completed", 0) * 1000)
        phase_pct = (phase_processed / TOTAL_COMPANIES) * 100
        phase_fresh = log_freshness.get("phase", {})
        status_icon = "🟢" if phase_fresh.get("is_fresh") else "🔴"
        print(f"  {status_icon} Phase log:     {phase_processed:,} companies ({phase_pct:.1f}%)")
    elif combined_stats.get("phase_error"):
        print(f"  ⚠️  Phase log:     Error - {combined_stats['phase_error']}")
    else:
        print("  ⚪ Phase log:     Not found")

    if continuous_stats:
        cont_processed = continuous_stats.get("chunks_completed", 0) * 1000
        cont_pct = (cont_processed / TOTAL_COMPANIES) * 100
        cont_fresh = log_freshness.get("continuous", {})
        status_icon = "🟢" if cont_fresh.get("is_fresh") else "🔴"
        print(f"  {status_icon} Continuous log: {cont_processed:,} companies ({cont_pct:.1f}%)")
    elif combined_stats.get("continuous_error"):
        print(f"  ⚠️  Continuous log: Error - {combined_stats['continuous_error']}")
    else:
        print("  ⚪ Continuous log: Not found")

    # Geocoding log status
    geocoding_stats = combined_stats.get("geocoding_stats")
    if geocoding_stats:
        geo_processed = geocoding_stats.get("chunks_completed", 0) * 500  # geocoding uses 500 limit
        geo_fresh = log_freshness.get("geocoding", {})
        status_icon = "🟢" if geo_fresh.get("is_fresh") else "🔴"
        print(f"  {status_icon} Geocoding log:  {geo_processed:,} companies processed")
    elif combined_stats.get("geocoding_error"):
        print(f"  ⚠️  Geocoding log:  Error - {combined_stats['geocoding_error']}")
    else:
        print("  ⚪ Geocoding log:  Not found")

    # Database Stats Section
    print("\n🗄️  DATABASE STATUS")
    print("-" * 40)

    if db_stats:
        if "error" in db_stats:
            print(f"  ⚠️  Database error: {db_stats['error']}")
        else:
            total = db_stats["total"]
            enriched = db_stats["enriched"]
            pending = db_stats["pending"]
            error = db_stats.get("error", 0)
            pct = db_stats["progress_pct"]

            bar_width = 30
            filled = int(bar_width * pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)

            print(f"  Total companies:     {total:,}")
            print(f"  Enriched:            {enriched:,} ({pct:.2f}%)")
            print(f"  Pending:             {pending:,} ({pending/total*100:.2f}%)")
            if error > 0:
                print(f"  Error:               {error:,}")
            print(f"  Progress:            [{bar}] {pct:.1f}%")
    else:
        print("  ℹ️  Database not available (set DATABASE_URL for DB stats)")

    # Recent Errors Section
    if combined_stats.get("recent_errors") and not args.no_errors:
        print("\n⚠️  RECENT ERRORS/WARNINGS")
        print("-" * 40)
        for err in combined_stats["recent_errors"][-5:]:
            if len(err) > 65:
                err = err[:62] + "..."
            print(f"  • {err}")

    print(f"\n{'='*70}")

    if args.watch:
        print("\n💡 Press Ctrl+C to exit watch mode")


def main():
    parser = argparse.ArgumentParser(
        description="Enrichment Progress Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/enrich_dashboard.py              # One-time snapshot
  python scripts/enrich_dashboard.py --watch      # Continuous updates
  python scripts/enrich_dashboard.py --log FILE   # Parse specific log
        """
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Watch mode: update every 30 seconds"
    )
    parser.add_argument(
        "--log", "-l",
        type=Path,
        help="Specific log file to parse (default: all logs combined)"
    )
    parser.add_argument(
        "--no-errors",
        action="store_true",
        help="Hide recent errors section"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=30,
        help="Update interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--verify", "-V",
        action="store_true",
        help="AGENTS.md compliance: Output verification commands and exit"
    )

    args = parser.parse_args()

    # AGENTS.md verification mode
    if args.verify:
        print("AGENTS.md Enrichment Verification Protocol")
        print("=" * 50)
        print("\nMandatory verification commands:")
        print("  1. python scripts/enrich_dashboard.py")
        print("  2. ps aux | grep -E '(enrich|geocoding)' | grep -v grep")
        print("  3. ls -lt logs/enrichment/ | head -5")
        print("  4. stat -c '%y' logs/enrichment/<current_log>")
        print("  5. tail -20 logs/enrichment/<current_log>")
        print("\nAcceptance criteria:")
        print("  ✓ Log timestamp < 2 hours old for 'running' claims")
        print("  ✓ Process state matches claimed status")
        print("  ✓ Dashboard output matches handoff stats")
        print("\nLog files found:")
        logs = find_all_logs()
        for log_name, log_path in logs.items():
            if log_path:
                freshness = check_log_freshness(log_path)
                status = "FRESH" if freshness["is_fresh"] else "STALE"
                print(f"  {log_name}: {log_path}")
                print(f"    Last modified: {freshness['mtime']}")
                print(f"    Age: {freshness['age_hours']:.2f} hours ({status})")
            else:
                print(f"  {log_name}: Not found")
        sys.exit(0)

    try:
        while True:
            # Clear screen in watch mode
            if args.watch:
                os.system("clear" if os.name != "nt" else "cls")

            # Get all log files
            if args.log:
                # Single log mode
                log_stats = {"single": parse_log_file(args.log)}
                combined = aggregate_log_stats(log_stats)
                log_freshness = {"single": check_log_freshness(args.log)}
            else:
                # Combined log mode
                logs = find_all_logs()
                log_stats = {}
                log_freshness = {}

                for log_name, log_path in logs.items():
                    if log_path:
                        log_stats[log_name] = parse_log_file(log_path)
                        log_freshness[log_name] = check_log_freshness(log_path)

                combined = aggregate_log_stats(log_stats)

            # Get other stats
            db_stats = asyncio.run(get_db_stats()) if HAS_DB else None
            process_health = check_process_health()

            # Print dashboard
            print_dashboard(db_stats, combined, log_freshness, process_health, args)

            if not args.watch:
                break

            # Wait for next update
            try:
                import time
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n\nExiting watch mode.")
                break

    except KeyboardInterrupt:
        print("\n\nExiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
