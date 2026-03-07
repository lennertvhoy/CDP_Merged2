#!/bin/bash
# backup_and_rollback.sh - Backup and rollback utilities for Tracardi data cleanup

set -e

# Configuration
ES_HOST="${ES_HOST:-http://localhost:9200}"
BACKUP_DIR="${BACKUP_DIR:-/backup/elasticsearch}"
INDEX_PATTERN="*tracardi-profile*"
DATE=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Elasticsearch connectivity
check_es() {
    log_info "Checking Elasticsearch connectivity..."
    if ! curl -s "${ES_HOST}/_cluster/health" > /dev/null 2>&1; then
        log_error "Cannot connect to Elasticsearch at ${ES_HOST}"
        exit 1
    fi
    log_info "Elasticsearch is reachable"
}

# Create snapshot repository
create_repo() {
    log_info "Creating snapshot repository..."
    
    mkdir -p "${BACKUP_DIR}"
    
    curl -s -X PUT "${ES_HOST}/_snapshot/cleanup_backup" \
        -H "Content-Type: application/json" \
        -d "{
            \"type\": \"fs\",
            \"settings\": {
                \"location\": \"${BACKUP_DIR}\"
            }
        }" | grep -q '"acknowledged":true' && log_info "Repository created" || log_warn "Repository may already exist"
}

# Create snapshot
backup() {
    check_es
    create_repo
    
    SNAPSHOT_NAME="pre_cleanup_${DATE}"
    log_info "Creating snapshot: ${SNAPSHOT_NAME}"
    
    # Start snapshot
    curl -s -X PUT "${ES_HOST}/_snapshot/cleanup_backup/${SNAPSHOT_NAME}" \
        -H "Content-Type: application/json" \
        -d "{
            \"indices\": \"${INDEX_PATTERN}\",
            \"ignore_unavailable\": true,
            \"include_global_state\": false
        }"
    
    log_info "Snapshot initiated, waiting for completion..."
    
    # Wait for snapshot to complete
    for i in {1..60}; do
        STATUS=$(curl -s "${ES_HOST}/_snapshot/cleanup_backup/${SNAPSHOT_NAME}/_status" | grep -o '"state":"[^"]*"' | cut -d'"' -f4)
        
        if [ "${STATUS}" = "SUCCESS" ]; then
            log_info "Snapshot completed successfully!"
            echo "${SNAPSHOT_NAME}" > "${BACKUP_DIR}/latest_snapshot.txt"
            return 0
        elif [ "${STATUS}" = "FAILED" ]; then
            log_error "Snapshot failed!"
            return 1
        fi
        
        sleep 5
    done
    
    log_warn "Snapshot still in progress, check manually with:"
    echo "curl -s ${ES_HOST}/_snapshot/cleanup_backup/${SNAPSHOT_NAME}/_status"
}

# List available snapshots
list_snapshots() {
    log_info "Available snapshots:"
    curl -s "${ES_HOST}/_snapshot/cleanup_backup/_all" | grep -o '"snapshot":"[^"]*"' | cut -d'"' -f4
}

# Restore from snapshot
restore() {
    SNAPSHOT_NAME="$1"
    
    if [ -z "${SNAPSHOT_NAME}" ]; then
        # Try to get latest
        if [ -f "${BACKUP_DIR}/latest_snapshot.txt" ]; then
            SNAPSHOT_NAME=$(cat "${BACKUP_DIR}/latest_snapshot.txt")
        else
            log_error "No snapshot name provided and no latest snapshot found"
            exit 1
        fi
    fi
    
    log_warn "About to restore from snapshot: ${SNAPSHOT_NAME}"
    log_warn "This will OVERWRITE current data!"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "${confirm}" != "yes" ]; then
        log_info "Restore cancelled"
        exit 0
    fi
    
    check_es
    
    log_info "Closing indices before restore..."
    curl -s -X POST "${ES_HOST}/_all/_close" | grep -q '"acknowledged":true' && log_info "Indices closed"
    
    log_info "Restoring from snapshot..."
    curl -s -X POST "${ES_HOST}/_snapshot/cleanup_backup/${SNAPSHOT_NAME}/_restore" \
        -H "Content-Type: application/json" \
        -d '{
            "include_global_state": false
        }'
    
    log_info "Restore initiated, opening indices..."
    curl -s -X POST "${ES_HOST}/_all/_open" | grep -q '"acknowledged":true' && log_info "Indices opened"
    
    log_info "Restore complete!"
}

# Export sample profiles to JSON
export_sample() {
    SAMPLE_SIZE="${1:-1000}"
    OUTPUT_FILE="sample_backup_${DATE}.json"
    
    log_info "Exporting ${SAMPLE_SIZE} sample profiles to ${OUTPUT_FILE}..."
    
    # Get actual index name
    INDEX_NAME=$(curl -s "${ES_HOST}/_cat/indices" | grep profile | head -1 | awk '{print $3}')
    
    if [ -z "${INDEX_NAME}" ]; then
        log_error "Could not find profile index"
        exit 1
    fi
    
    curl -s -X POST "${ES_HOST}/${INDEX_NAME}/_search" \
        -H "Content-Type: application/json" \
        -d "{
            \"size\": ${SAMPLE_SIZE},
            \"query\": {\"match_all\": {}},
            \"sort\": [{\"metadata.time.insert\": \"desc\"}]
        }" > "${OUTPUT_FILE}"
    
    log_info "Sample exported to ${OUTPUT_FILE}"
    log_info "File size: $(du -h "${OUTPUT_FILE}" | cut -f1)"
}

# Create index alias for safe switching
create_alias() {
    INDEX_NAME="$1"
    ALIAS_NAME="tracardi-profiles"
    
    log_info "Creating alias ${ALIAS_NAME} -> ${INDEX_NAME}"
    
    curl -s -X POST "${ES_HOST}/_aliases" \
        -H "Content-Type: application/json" \
        -d "{
            \"actions\": [
                { \"add\": { \"index\": \"${INDEX_NAME}\", \"alias\": \"${ALIAS_NAME}\" } }
            ]
        }" | grep -q '"acknowledged":true' && log_info "Alias created" || log_error "Failed to create alias"
}

# Switch alias to new index (for blue-green deployments)
switch_alias() {
    OLD_INDEX="$1"
    NEW_INDEX="$2"
    ALIAS_NAME="tracardi-profiles"
    
    log_info "Switching alias ${ALIAS_NAME} from ${OLD_INDEX} to ${NEW_INDEX}"
    
    curl -s -X POST "${ES_HOST}/_aliases" \
        -H "Content-Type: application/json" \
        -d "{
            \"actions\": [
                { \"remove\": { \"index\": \"${OLD_INDEX}\", \"alias\": \"${ALIAS_NAME}\" } },
                { \"add\": { \"index\": \"${NEW_INDEX}\", \"alias\": \"${ALIAS_NAME}\" } }
            ]
        }" | grep -q '"acknowledged":true' && log_info "Alias switched" || log_error "Failed to switch alias"
}

# Check cleanup progress
check_progress() {
    INDEX_NAME=$(curl -s "${ES_HOST}/_cat/indices" | grep profile | head -1 | awk '{print $3}')
    
    log_info "Checking cleanup progress..."
    
    # Count profiles with cleanup marker
    CLEANED=$(curl -s -X POST "${ES_HOST}/${INDEX_NAME}/_count" \
        -H "Content-Type: application/json" \
        -d '{"query": {"exists": {"field": "traits._cleanup_version"}}}')
    
    TOTAL=$(curl -s "${ES_HOST}/${INDEX_NAME}/_count")
    
    CLEANED_COUNT=$(echo "${CLEANED}" | grep -o '"count":[0-9]*' | cut -d':' -f2)
    TOTAL_COUNT=$(echo "${TOTAL}" | grep -o '"count":[0-9]*' | cut -d':' -f2)
    
    if [ -n "${CLEANED_COUNT}" ] && [ -n "${TOTAL_COUNT}" ] && [ "${TOTAL_COUNT}" -gt 0 ]; then
        PCT=$((CLEANED_COUNT * 100 / TOTAL_COUNT))
        log_info "Progress: ${CLEANED_COUNT}/${TOTAL_COUNT} (${PCT}%) profiles cleaned"
    else
        log_warn "Could not determine progress"
    fi
}

# Usage
usage() {
    cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

Commands:
    backup              Create full Elasticsearch snapshot
    list                List available snapshots
    restore [NAME]      Restore from snapshot (latest if no name provided)
    export [N]          Export N sample profiles (default: 1000)
    alias INDEX         Create alias for index
    switch OLD NEW      Switch alias to new index
    progress            Check cleanup progress
    help                Show this help

Environment Variables:
    ES_HOST             Elasticsearch URL (default: http://localhost:9200)
    BACKUP_DIR          Backup directory (default: /backup/elasticsearch)

Examples:
    $0 backup                              # Create snapshot
    $0 restore pre_cleanup_20260225        # Restore specific snapshot
    $0 export 5000                         # Export 5000 samples
    $0 progress                            # Check cleanup progress
EOF
}

# Main
case "${1:-help}" in
    backup)
        backup
        ;;
    list)
        list_snapshots
        ;;
    restore)
        restore "$2"
        ;;
    export)
        export_sample "$2"
        ;;
    alias)
        create_alias "$2"
        ;;
    switch)
        switch_alias "$2" "$3"
        ;;
    progress)
        check_progress
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        log_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac
