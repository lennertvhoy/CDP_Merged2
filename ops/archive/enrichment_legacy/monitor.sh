#!/bin/bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
while true; do
    clear
    echo "=== CDP Phase 2 Enrichment Monitor ==="
    echo "Time: $(date '+%H:%M:%S')"
    echo ""
    echo "--- Progress ---"
    OFFSET=$(jq -r '.last_offset' data/progress/streaming_last_offset_phase2_cbe_integration.json 2>/dev/null)
    TOTAL=1813016
    PCT=$(( OFFSET * 100 / TOTAL ))
    echo "Progress: $OFFSET / $TOTAL ($PCT%)"
    echo "Updated: $(jq -r '.updated_at' data/progress/streaming_last_offset_phase2_cbe_integration.json 2>/dev/null)"
    echo ""
    echo "--- Process Status ---"
    PID=$(pgrep -f "python.*enrich" | head -1)
    if [ -n "$PID" ]; then
        echo "✅ Running (PID: $PID)"
        ps -o etime,pcpu,pmem -p $PID 2>/dev/null | tail -1
    else
        echo "❌ Not running"
    fi
    echo ""
    echo "--- Latest Log Entries ---"
    tail -3 logs/enrichment_phase2_live.log 2>/dev/null | jq -r '"\(.timestamp[11:19]) \(.event[0:50])"' 2>/dev/null || tail -2 logs/enrichment_phase2_live.log
    echo ""
    echo "Refreshing in 10s... (Ctrl+C to stop)"
    sleep 10
done
