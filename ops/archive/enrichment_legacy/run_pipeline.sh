#!/bin/bash
export TRACARDI_API_URL="http://52.148.232.140:8686"
export TRACARDI_USERNAME="admin@cdpmerged.local"
export TRACARDI_PASSWORD="admin"
export TRACARDI_SOURCE_ID="kbo-source"

LOG_FILE="logs/enrichment_$(date +%Y-%m-%d).log"

echo "Starting Phases 1-5..." > $LOG_FILE
nohup poetry run python run_enrichment_streaming.py >> $LOG_FILE 2>&1 &
echo $! > enrichment_pid.txt
echo "Enrichment pipeline started in background with PID $(cat enrichment_pid.txt)."
