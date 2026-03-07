#!/bin/bash
# Auto-check enrichment progress every 30 minutes

LOGFILE="/home/ff/.openclaw/workspace/repos/CDP_Merged/logs/enrichment_$(date +%Y%m%d)*.log"
LATEST_LOG=$(ls -t /home/ff/.openclaw/workspace/repos/CDP_Merged/logs/enrichment_20260227_*.log 2>/dev/null | head -1)

# Check if process is running
PID=$(pgrep -f "run_enrichment_streaming" | head -1)

if [ -z "$PID" ]; then
    echo "$(date): ❌ ENRICHMENT STOPPED - Process not found"
    echo "$(date): ❌ ENRICHMENT STOPPED - Process not found" >> /home/ff/.openclaw/workspace/repos/CDP_Merged/logs/enrichment_monitor.log
    # Could add restart logic here
else
    # Get latest progress from log
    if [ -f "$LATEST_LOG" ]; then
        PROGRESS=$(tail -1 "$LATEST_LOG" | grep -oE "processed [0-9]+" | tail -1 || echo "N/A")
        echo "$(date): ✅ Running (PID: $PID) - $PROGRESS profiles"
        echo "$(date): ✅ Running (PID: $PID) - $PROGRESS profiles" >> /home/ff/.openclaw/workspace/repos/CDP_Merged/logs/enrichment_monitor.log
    else
        echo "$(date): ⚠️ Running (PID: $PID) - No log file found"
    fi
fi
