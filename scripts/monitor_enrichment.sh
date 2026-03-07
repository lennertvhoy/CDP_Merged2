#!/bin/bash
# CDP_Merged Enrichment Progress Monitor
# Runs every 30 minutes, reports only on significant events

WORKSPACE="/home/ff/.openclaw/workspace/repos/CDP_Merged"
LOG_FILE="$WORKSPACE/logs/enrichment_phase1_live.log"
PROGRESS_DIR="$WORKSPACE/data/progress"
STATE_FILE="$WORKSPACE/.enrichment_monitor_state"
NOTIFY_CHANNEL="telegram"

# Read last known progress
get_current_progress() {
    if [ -f "$LOG_FILE" ]; then
        # Extract latest progress line
        tail -100 "$LOG_FILE" | grep -o '"progress":[0-9.]*%' | tail -1 | tr -d '"progress:%'
    else
        echo "0"
    fi
}

# Get processed count
get_processed_count() {
    if [ -f "$LOG_FILE" ]; then
        tail -100 "$LOG_FILE" | grep -o '"processed":[0-9]*' | tail -1 | tr -d '"processed:'
    else
        echo "0"
    fi
}

# Check if process is running
check_process_running() {
    pgrep -f "enrich_profiles.py.*phase1_contact_validation" > /dev/null
    return $?
}

# Check for errors in last 100 lines
check_for_errors() {
    if [ -f "$LOG_FILE" ]; then
        tail -100 "$LOG_FILE" | grep -i '"level":"error"' | wc -l
    else
        echo "0"
    fi
}

# Main monitoring logic
main() {
    CURRENT_PROGRESS=$(get_current_progress)
    PROCESSED=$(get_processed_count)
    ERRORS=$(check_for_errors)
    
    # Read previous state
    if [ -f "$STATE_FILE" ]; then
        source "$STATE_FILE"
    else
        LAST_PROGRESS="0"
        LAST_STATUS="unknown"
    fi
    
    # Check if process died
    if ! check_process_running; then
        if [ "$LAST_STATUS" != "completed" ] && [ "$LAST_STATUS" != "failed" ]; then
            # Process stopped unexpectedly
            echo "status=failed" > "$STATE_FILE"
            echo "progress=$CURRENT_PROGRESS" >> "$STATE_FILE"
            echo "processed=$PROCESSED" >> "$STATE_FILE"
            echo "timestamp=$(date -Iseconds)" >> "$STATE_FILE"
            
            # Send notification
            curl -s -X POST "http://localhost:8080/api/message" \
                -H "Content-Type: application/json" \
                -d "{\"channel\":\"$NOTIFY_CHANNEL\",\"message\":\"🚨 CDP Enrichment STOPPED unexpectedly!\nProgress: ${CURRENT_PROGRESS}%\nProcessed: ${PROCESSED}/1,813,016\nCheck logs: logs/enrichment_phase1_live.log\"}" 2>/dev/null
            exit 1
        fi
    fi
    
    # Check for completion
    if (( $(echo "$CURRENT_PROGRESS >= 99.9" | bc -l) )); then
        if [ "$LAST_STATUS" != "completed" ]; then
            echo "status=completed" > "$STATE_FILE"
            echo "progress=$CURRENT_PROGRESS" >> "$STATE_FILE"
            echo "processed=$PROCESSED" >> "$STATE_FILE"
            echo "timestamp=$(date -Iseconds)" >> "$STATE_FILE"
            
            # Send completion notification
            curl -s -X POST "http://localhost:8080/api/message" \
                -H "Content-Type: application/json" \
                -d "{\"channel\":\"$NOTIFY_CHANNEL\",\"message\":\"✅ CDP Phase 1 Enrichment COMPLETE!\nProgress: ${CURRENT_PROGRESS}%\nProcessed: ${PROCESSED}/1,813,016\nErrors: ${ERRORS}\nReady for Phase 2 (website discovery).\"}" 2>/dev/null
        fi
        exit 0
    fi
    
    # Check if stalled (no progress for 2 checks = 1 hour)
    if [ "$CURRENT_PROGRESS" == "$LAST_PROGRESS" ] && [ "$LAST_STATUS" == "running" ]; then
        # Check if we already flagged as stalled
        if [ -f "$STATE_FILE.stalled" ]; then
            STALL_TIME=$(cat "$STATE_FILE.stalled")
            CURRENT_TIME=$(date +%s)
            STALL_DURATION=$((CURRENT_TIME - STALL_TIME))
            
            if [ $STALL_DURATION -gt 3600 ]; then
                # Stalled for over an hour
                curl -s -X POST "http://localhost:8080/api/message" \
                    -H "Content-Type: application/json" \
                    -d "{\"channel\":\"$NOTIFY_CHANNEL\",\"message\":\"⚠️ CDP Enrichment STALLED for 1+ hour!\nProgress stuck at: ${CURRENT_PROGRESS}%\nProcessed: ${PROCESSED}\nCheck logs immediately.\"}" 2>/dev/null
                rm -f "$STATE_FILE.stalled"
            fi
        else
            # First stall detection
            date +%s > "$STATE_FILE.stalled"
        fi
    else
        # Progress resumed or progressing
        rm -f "$STATE_FILE.stalled"
    fi
    
    # Check for significant errors (>10 errors in last 100 lines)
    if [ "$ERRORS" -gt 10 ]; then
        if [ "$LAST_ERROR_COUNT" != "$ERRORS" ]; then
            curl -s -X POST "http://localhost:8080/api/message" \
                -H "Content-Type: application/json" \
                -d "{\"channel\":\"$NOTIFY_CHANNEL\",\"message\":\"⚠️ CDP Enrichment showing errors!\nErrors in last 100 lines: ${ERRORS}\nProgress: ${CURRENT_PROGRESS}%\nCheck logs for details.\"}" 2>/dev/null
        fi
    fi
    
    # Save current state
    echo "status=running" > "$STATE_FILE"
    echo "progress=$CURRENT_PROGRESS" >> "$STATE_FILE"
    echo "processed=$PROCESSED" >> "$STATE_FILE"
    echo "timestamp=$(date -Iseconds)" >> "$STATE_FILE"
    echo "error_count=$ERRORS" >> "$STATE_FILE"
    
    # Silent success - no notification needed
    exit 0
}

main
