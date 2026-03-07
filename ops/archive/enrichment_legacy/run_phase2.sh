#!/bin/bash
# CDP Phase 2 Runner - Auto-restart on exit with memory protection
WORKSPACE="/home/ff/.openclaw/workspace/repos/CDP_Merged"
LOG="$WORKSPACE/logs/enrichment_phase2_live.log"
ERROR_LOG="$WORKSPACE/logs/enrichment_errors.log"

cd "$WORKSPACE"
set -o pipefail

# Memory protection - if we get OOM-killed too many times, slow down
CONSECUTIVE_OOM=0
MAX_CONSECUTIVE_OOM=3

while true; do
    echo "[$(date)] Starting CBE Phase 2..." >> "$LOG"
    echo "[$(date)] Starting CBE Phase 2..." >> "$ERROR_LOG"
    
    # Run enrichment directly (not in timeout sub-shell)
    poetry run python scripts/enrich_profiles.py \
        --phase phase2_cbe_integration \
        --live \
        --batch-size 25 \
        --limit 2000000 \
        --log-level INFO 2>> "$ERROR_LOG" | tee -a "$LOG"
    
    EXIT_CODE=${PIPESTATUS[0]}
    echo "[$(date)] Exited with code $EXIT_CODE" >> "$LOG"
    echo "[$(date)] Exited with code $EXIT_CODE" >> "$ERROR_LOG"
    
    # Handle specific exit codes
    if [ $EXIT_CODE -eq 137 ]; then
        CONSECUTIVE_OOM=$((CONSECUTIVE_OOM + 1))
        echo "[$(date)] WARNING: Process was OOM-killed (exit 137). Consecutive OOMs: $CONSECUTIVE_OOM" >> "$ERROR_LOG"
        
        if [ $CONSECUTIVE_OOM -ge $MAX_CONSECUTIVE_OOM ]; then
            echo "[$(date)] ERROR: Too many consecutive OOM kills. Waiting 60 seconds..." >> "$ERROR_LOG"
            sleep 60
            CONSECUTIVE_OOM=0
        else
            echo "[$(date)] Waiting 30 seconds for memory cleanup..." >> "$ERROR_LOG"
            sleep 30
        fi
        continue
    elif [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date)] Process completed successfully" >> "$LOG"
        CONSECUTIVE_OOM=0
    else
        echo "[$(date)] Process exited with code $EXIT_CODE" >> "$ERROR_LOG"
        CONSECUTIVE_OOM=0
    fi
    
    # Check if completed (checkpoint file removed by successful completion)
    if [ ! -f "$WORKSPACE/data/progress/streaming_last_offset_phase2_cbe_integration.json" ]; then
        echo "[$(date)] Phase 2 COMPLETE!" >> "$LOG"
        echo "[$(date)] Phase 2 COMPLETE!" >> "$ERROR_LOG"
        exit 0
    fi
    
    # Brief pause before restart
    echo "[$(date)] Restarting in 10 seconds..." >> "$LOG"
    sleep 10
done
