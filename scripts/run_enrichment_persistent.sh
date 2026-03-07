#!/bin/bash
# Restartable wrapper around the chunked companies enricher.

set -o pipefail

WORKSPACE="/home/ff/.openclaw/workspace/repos/CDP_Merged"
ENRICHERS="${ENRICHERS:-cbe}"
RUN_NAME="${RUN_NAME:-${ENRICHERS//,/__}}"
CHUNK_SIZE="${CHUNK_SIZE:-2000}"
BATCH_SIZE="${BATCH_SIZE:-1000}"
PAUSE_SECONDS="${PAUSE_SECONDS:-1}"
RESTART_DELAY_SECONDS="${RESTART_DELAY_SECONDS:-10}"
LOG_DIR="$WORKSPACE/logs/enrichment"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_FILE:-$LOG_DIR/${RUN_NAME}_${TIMESTAMP}.log}"
ERROR_LOG="${ERROR_LOG:-$LOG_DIR/${RUN_NAME}_supervisor.log}"
CURSOR_FILE="${CURSOR_FILE:-$LOG_DIR/${RUN_NAME}_cursor.json}"
PID_FILE="${PID_FILE:-$WORKSPACE/.${RUN_NAME}_runner.pid}"

mkdir -p "$LOG_DIR"

# Save PID
echo $$ > "$PID_FILE"

cleanup() {
    rm -f "$PID_FILE"
    exit 0
}
trap cleanup EXIT

if command -v poetry >/dev/null 2>&1; then
    PYTHON_CMD=(poetry run python)
else
    PYTHON_CMD=(python)
fi

echo "[$(date)] Enrichment runner started (PID: $$, enrichers=$ENRICHERS, cursor=$CURSOR_FILE)" >> "$ERROR_LOG"

while true; do
    if pgrep -f "scripts/enrich_companies_chunked.py.*--enrichers ${ENRICHERS}" > /dev/null; then
        echo "[$(date)] Enrichment already running, waiting..." >> "$ERROR_LOG"
        sleep 60
        continue
    fi

    echo "[$(date)] Starting enrichment..." >> "$ERROR_LOG"

    cd "$WORKSPACE"
    "${PYTHON_CMD[@]}" scripts/enrich_companies_chunked.py \
        --enrichers "$ENRICHERS" \
        --chunk-size "$CHUNK_SIZE" \
        --batch-size "$BATCH_SIZE" \
        --pause "$PAUSE_SECONDS" \
        --cursor-file "$CURSOR_FILE" \
        2>&1 | tee -a "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}
    echo "[$(date)] Enrichment exited with code $EXIT_CODE" >> "$ERROR_LOG"

    if [ "$EXIT_CODE" -eq 0 ]; then
        echo "[$(date)] Enrichment completed successfully!" >> "$ERROR_LOG"
        exit 0
    fi

    echo "[$(date)] Restarting in ${RESTART_DELAY_SECONDS} seconds..." >> "$ERROR_LOG"
    sleep "$RESTART_DELAY_SECONDS"
done
