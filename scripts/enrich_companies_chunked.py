#!/usr/bin/env python3
"""
Chunked enrichment runner - processes companies in manageable batches
to avoid loading all 1.9M companies into memory at once.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Configuration
CHUNK_SIZE = 10000  # Process 10k companies at a time
BATCH_SIZE = 500  # Internal batch size for the enrichment script
PAUSE_BETWEEN_CHUNKS = 5  # Seconds to pause between chunks


def run_chunk(
    limit: int,
    start_after_id: str | None = None,
    enrichers: str = "cbe",
    batch_size: int = BATCH_SIZE,
) -> dict:
    """Run enrichment for a single chunk."""
    cmd = [
        sys.executable,
        "-u",
        "scripts/enrich_companies_batch.py",
        "--enrichers",
        enrichers,
        "--batch-size",
        str(batch_size),
        "--limit",
        str(limit),
    ]
    if start_after_id is not None:
        cmd.extend(["--start-after-id", start_after_id])

    env = os.environ.copy()
    cwd = str(Path.cwd())
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{cwd}:{existing_pythonpath}" if existing_pythonpath else cwd
    env["PYTHONUNBUFFERED"] = "1"

    print(f"\n{'=' * 60}")
    print(f"Running chunk: start_after_id={start_after_id or 'START'}, limit={limit}")
    print(f"{'=' * 60}")

    stdout_lines: list[str] = []
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        stdout_lines.append(line)

    returncode = process.wait()
    stdout = "".join(stdout_lines)

    return {
        "returncode": returncode,
        "stdout": stdout,
        "stderr": "",
    }


def parse_stats(output: str) -> dict:
    """Parse enrichment stats from output."""
    stats = {
        "processed": 0,
        "enriched": 0,
        "skipped": 0,
        "failed": 0,
        "last_company_id": None,
    }
    for line in output.split("\n"):
        if "Total processed:" in line:
            match = re.search(r"Total processed:\s*([\d,]+)", line)
            if match:
                stats["processed"] = int(match.group(1).replace(",", ""))
        elif "Enriched:" in line and "Geocoding" not in line and "CBE enrichments" not in line:
            match = re.search(r"Enriched:\s*([\d,]+)", line)
            if match:
                stats["enriched"] = int(match.group(1).replace(",", ""))
        elif "Skipped:" in line:
            match = re.search(r"Skipped:\s*([\d,]+)", line)
            if match:
                stats["skipped"] = int(match.group(1).replace(",", ""))
        elif "Failed:" in line and "Errors:" not in line:
            match = re.search(r"Failed:\s*([\d,]+)", line)
            if match:
                stats["failed"] = int(match.group(1).replace(",", ""))
        elif "Last company ID:" in line:
            last_company_id = line.split("Last company ID:", 1)[1].strip()
            if last_company_id and last_company_id.lower() != "n/a":
                stats["last_company_id"] = last_company_id
    return stats


def load_cursor(cursor_file: Path) -> str | None:
    """Load the last processed company UUID from disk."""
    if not cursor_file.exists():
        return None

    try:
        payload = json.loads(cursor_file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARNING: Could not read cursor file {cursor_file}: {exc}")
        return None

    cursor = payload.get("start_after_id")
    if isinstance(cursor, str) and cursor:
        return cursor
    return None


def save_cursor(cursor_file: Path, start_after_id: str | None, completed: bool) -> None:
    """Persist the last processed company UUID for restartable runs."""
    cursor_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "start_after_id": start_after_id,
        "completed": completed,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    cursor_file.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Chunked enrichment runner")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNK_SIZE,
        help=f"Companies per chunk (default: {CHUNK_SIZE})",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Maximum number of chunks to process (default: unlimited)",
    )
    parser.add_argument(
        "--pause",
        type=int,
        default=PAUSE_BETWEEN_CHUNKS,
        help=f"Seconds to pause between chunks (default: {PAUSE_BETWEEN_CHUNKS})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Internal batch size for each chunk (default: {BATCH_SIZE})",
    )
    parser.add_argument(
        "--enrichers",
        type=str,
        default="cbe",
        help="Comma-separated list of enrichers to run (default: cbe)",
    )
    parser.add_argument(
        "--start-after-id", type=str, default=None, help="Resume strictly after this company UUID"
    )
    parser.add_argument(
        "--cursor-file",
        type=Path,
        default=None,
        help="Optional JSON file to persist the last processed company UUID",
    )

    args = parser.parse_args()

    total_stats = {
        "chunks": 0,
        "processed": 0,
        "enriched": 0,
        "skipped": 0,
        "failed": 0,
    }

    chunk = 0
    start_after_id = args.start_after_id
    if start_after_id is None and args.cursor_file is not None:
        start_after_id = load_cursor(args.cursor_file)
        if start_after_id:
            print(f"Resuming from cursor file {args.cursor_file}: {start_after_id}")

    exit_code = 0

    try:
        while args.max_chunks is None or chunk < args.max_chunks:
            result = run_chunk(
                args.chunk_size,
                start_after_id=start_after_id,
                enrichers=args.enrichers,
                batch_size=args.batch_size,
            )

            if result["returncode"] != 0:
                print(f"ERROR: Chunk {chunk} failed with return code {result['returncode']}")
                print(result["stderr"])
                exit_code = result["returncode"] or 1
                break

            stats = parse_stats(result["stdout"])

            total_stats["chunks"] += 1
            total_stats["processed"] += stats["processed"]
            total_stats["enriched"] += stats["enriched"]
            total_stats["skipped"] += stats["skipped"]
            total_stats["failed"] += stats["failed"]

            print(f"\nChunk {chunk} complete. Running totals:")
            print(f"  Processed: {total_stats['processed']:,}")
            print(f"  Enriched: {total_stats['enriched']:,}")
            print(f"  Skipped: {total_stats['skipped']:,}")
            print(f"  Failed: {total_stats['failed']:,}")

            # If we processed fewer companies than the chunk size, we're done
            if stats["processed"] < args.chunk_size:
                print("\nAll companies processed!")
                break

            if not stats["last_company_id"]:
                print(
                    "\nERROR: Chunk did not report a last company ID, cannot advance cursor safely."
                )
                exit_code = 1
                break

            start_after_id = stats["last_company_id"]
            if args.cursor_file is not None:
                save_cursor(args.cursor_file, start_after_id, completed=False)

            chunk += 1

            if args.pause > 0:
                print(f"Pausing for {args.pause} seconds...")
                time.sleep(args.pause)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        exit_code = 130

    if args.cursor_file is not None:
        save_cursor(
            args.cursor_file,
            start_after_id,
            completed=exit_code == 0
            and total_stats["processed"] > 0
            and total_stats["processed"] % args.chunk_size != 0,
        )

    print(f"\n{'=' * 60}")
    print("ENRICHMENT RUN COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total chunks: {total_stats['chunks']}")
    print(f"Total processed: {total_stats['processed']:,}")
    print(f"Total enriched: {total_stats['enriched']:,}")
    print(f"Total skipped: {total_stats['skipped']:,}")
    print(f"Total failed: {total_stats['failed']:,}")
    print(f"{'=' * 60}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
