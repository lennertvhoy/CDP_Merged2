#!/bin/bash
# Enrichment Progress Monitor - Runs via cron every 15 minutes

cd /home/ff/.openclaw/workspace/repos/CDP_Merged
LOG_FILE="/home/ff/.openclaw/workspace/logs/enrichment_monitor_$(date +%Y%m%d).log"

echo "=== ENRICHMENT CHECK-IN [$(date '+%H:%M')] ===" | tee -a "$LOG_FILE"

# Check if enrichment process is running
ENRICH_PID=$(pgrep -f "run_enrichment|pipeline.py" | head -1)

if [ -n "$ENRICH_PID" ]; then
    # Get runtime
    RUNTIME=$(ps -o etime= -p "$ENRICH_PID" 2>/dev/null | tr -d ' ')
    echo "Status: RUNNING (PID: $ENRICH_PID, Runtime: $RUNTIME)" | tee -a "$LOG_FILE"
    
    # Get latest log progress
    LATEST_LOG=$(ls -t logs/enrichment*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        PROGRESS=$(tail -5 "$LATEST_LOG" 2>/dev/null | grep -E "processed|Phase" | tail -1)
        echo "Progress: $PROGRESS" | tee -a "$LOG_FILE"
    fi
    
    # Get current coverage
    TOKEN=$(curl -s -X POST "http://52.148.232.140:8686/user/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=admin@cdpmerged.local&password=<redacted>" \
        --max-time 8 2>/dev/null | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
    
    if [ -n "$TOKEN" ]; then
        echo "Coverage:" | tee -a "$LOG_FILE"
        for field in email phone discovered_website ai_description geo_latitude; do
            COUNT=$(curl -s -X POST "http://52.148.232.140:8686/profile/select" \
                -H "Authorization: Bearer $TOKEN" \
                -H "Content-Type: application/json" \
                -d "{\"where\":\"traits.$field EXISTS\",\"limit\":1}" \
                --max-time 5 2>/dev/null | \
                python3 -c "import sys,json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null)
            printf "  %s: %s\n" "$field" "$COUNT" | tee -a "$LOG_FILE"
        done
    fi
else
    echo "Status: NOT RUNNING" | tee -a "$LOG_FILE"
    echo "Enrichment process not found - may have completed or crashed" | tee -a "$LOG_FILE"
fi

echo "---" | tee -a "$LOG_FILE"
