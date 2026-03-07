#!/bin/bash
# KBO Import Manager - Controls the import process
# Usage: ./kbo_import_manager.sh {start|stop|status|logs|restart}

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="kbo-import"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$LOG_DIR/kbo_import.pid"
STATE_FILE="$LOG_DIR/import_kbo_state.json"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/manager.log"
}

get_status() {
    if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}

cmd_start() {
    local status=$(get_status)
    if [ "$status" = "running" ]; then
        log_msg "Service already running"
        return 0
    fi
    
    log_msg "Starting KBO import service..."
    
    # Reload systemd to pick up any changes
    systemctl --user daemon-reload
    
    # Start the service
    systemctl --user start "$SERVICE_NAME"
    
    sleep 1
    
    if [ "$(get_status)" = "running" ]; then
        log_msg "Service started successfully"
        log_msg "PID: $(systemctl --user show -p MainPID "$SERVICE_NAME" | cut -d= -f2)"
        log_msg "Logs: tail -f $LOG_DIR/import_kbo.log"
    else
        log_msg "ERROR: Failed to start service"
        log_msg "Check: journalctl --user -u $SERVICE_NAME -n 20"
        return 1
    fi
}

cmd_stop() {
    local status=$(get_status)
    if [ "$status" = "stopped" ]; then
        log_msg "Service already stopped"
        return 0
    fi
    
    log_msg "Stopping KBO import service..."
    
    # Graceful stop (sends SIGTERM, waits 30s, then SIGKILL)
    systemctl --user stop "$SERVICE_NAME"
    
    sleep 1
    
    if [ "$(get_status)" = "stopped" ]; then
        log_msg "Service stopped successfully"
    else
        log_msg "WARNING: Service may not have stopped cleanly"
    fi
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

cmd_status() {
    local status=$(get_status)
    echo "Service status: $status"
    
    if [ "$status" = "running" ]; then
        local pid=$(systemctl --user show -p MainPID "$SERVICE_NAME" | cut -d= -f2)
        local uptime=$(systemctl --user show -p ActiveEnterTimestamp "$SERVICE_NAME" | cut -d= -f2)
        echo "PID: $pid"
        echo "Started: $uptime"
        
        # Show recent progress
        if [ -f "$LOG_DIR/import_kbo.log" ]; then
            echo ""
            echo "--- Recent Progress ---"
            grep "Progress:" "$LOG_DIR/import_kbo.log" | tail -5
        fi
    fi
    
    # Show saved state
    if [ -f "$STATE_FILE" ]; then
        echo ""
        echo "--- Saved State ---"
        cat "$STATE_FILE"
    fi
    
    # Show database count
    echo ""
    echo "--- Database Status ---"
    if [ -n "${DATABASE_URL:-}" ]; then
        psql "$DATABASE_URL" -c "SELECT COUNT(*) as companies FROM companies;" 2>/dev/null || echo "(Could not query database)"
    else
        echo "(DATABASE_URL not set)"
    fi
}

cmd_logs() {
    local lines="${1:-50}"
    if [ -f "$LOG_DIR/import_kbo.log" ]; then
        echo "=== Import Log (last $lines lines) ==="
        tail -n "$lines" "$LOG_DIR/import_kbo.log"
    else
        echo "No import log found"
    fi
    
    echo ""
    echo "=== Systemd Journal (last $lines lines) ==="
    journalctl --user -u "$SERVICE_NAME" -n "$lines" --no-pager 2>/dev/null || echo "(No journal entries)"
}

cmd_monitor() {
    echo "Monitoring KBO import (Ctrl+C to exit)..."
    echo ""
    
    while true; do
        clear
        echo "=== KBO Import Monitor ==="
        echo "Time: $(date)"
        echo ""
        
        cmd_status
        
        echo ""
        echo "Refreshing in 10 seconds..."
        sleep 10
    done
}

# Main
case "${1:-status}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs "${2:-50}"
        ;;
    monitor)
        cmd_monitor
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|monitor}"
        echo ""
        echo "Commands:"
        echo "  start     - Start the import service"
        echo "  stop      - Stop the import service (graceful shutdown)"
        echo "  restart   - Restart the import service"
        echo "  status    - Show current status and progress"
        echo "  logs [N]  - Show last N lines of logs (default: 50)"
        echo "  monitor   - Live monitoring (refreshes every 10s)"
        exit 1
        ;;
esac
