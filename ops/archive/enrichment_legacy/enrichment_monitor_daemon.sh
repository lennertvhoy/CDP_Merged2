#!/bin/bash
# Simple background enrichment monitor
# Run this manually: nohup bash enrichment_monitor_daemon.sh &

LOG_FILE="/home/ff/.openclaw/workspace/logs/enrichment_monitor_daemon.log"
CHECK_INTERVAL=900  # 15 minutes

echo "=== ENRICHMENT MONITOR DAEMON STARTED ===" >> "$LOG_FILE"
echo "PID: $$, Started: $(date)" >> "$LOG_FILE"
echo "Checking every 15 minutes" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"

while true; do
    {
        echo "=== CHECK-IN [$(date '+%Y-%m-%d %H:%M')] ==="
        
        # Check enrichment process
        ENRICH_PID=$(pgrep -f "run_enrichment|pipeline.py" | head -1)
        
        if [ -n "$ENRICH_PID" ]; then
            RUNTIME=$(ps -o etime= -p "$ENRICH_PID" 2>/dev/null | tr -d ' ')
            echo "Status: RUNNING (PID: $ENRICH_PID, Runtime: $RUNTIME)"
            
            # Get progress
            LATEST_LOG=$(ls -t /home/ff/.openclaw/workspace/repos/CDP_Merged/logs/enrichment*.log 2>/dev/null | head -1)
            if [ -n "$LATEST_LOG" ]; then
                PROGRESS=$(tail -3 "$LATEST_LOG" 2>/dev/null | grep -E "processed|Phase" | tail -1)
                echo "Progress: $PROGRESS"
            fi
            
            # Get coverage
            TOKEN=$(curl -s -X POST "http://52.148.232.140:8686/user/token" \
                -H "Content-Type: application/x-www-form-urlencoded" \
                -d "username=admin@cdpmerged.local&password=<redacted>" \
                --max-time 8 2>/dev/null | \
                python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
            
            if [ -n "$TOKEN" ]; then
                echo "Coverage:"
                for field in email phone discovered_website ai_description geo_latitude; do
                    COUNT=$(curl -s -X POST "http://52.148.232.140:8686/profile/select" \
                        -H "Authorization: Bearer $TOKEN" \
                        -H "Content-Type: application/json" \
                        -d "{\"where\":\"traits.$field EXISTS\",\"limit\":1}" \
                        --max-time 5 2>/dev/null | \
                        python3 -c "import sys,json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null)
                    printf "  %s: %s\n" "$field" "$COUNT"
                done
            fi
        else
            echo "Status: NOT RUNNING - Enrichment may have completed or crashed"
        fi
        
        echo "---"
    } >> "$LOG_FILE"
    
    sleep $CHECK_INTERVAL
done
