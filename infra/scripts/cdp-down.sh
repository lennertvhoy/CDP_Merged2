#!/bin/bash
#===============================================================================
# CDP Down - Backup & Teardown Script
#===============================================================================
# Backs up PostgreSQL, deallocates VMs, stops PostgreSQL, scales down
# Container App. Reduces monthly cost from ~€200+ to ~€15-30.
#
# Usage: bash cdp-down.sh [--skip-backup] [--dry-run]
#===============================================================================

set -euo pipefail

RESOURCE_GROUP="rg-cdpmerged-fast"
POSTGRES_SERVER="cdp-postgres-661"
TRACARDI_VM="vm-tracardi-cdpmerged-prod"
DATA_VM="vm-data-cdpmerged-prod"
CONTAINER_APP="ca-cdpmerged-fast"
BACKUP_DIR="${CDP_BACKUP_DIR:-$HOME/cdp-backups}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠${NC}  $1"; }
err()  { echo -e "${RED}[$(date '+%H:%M:%S')] ✗${NC}  $1"; }
ok()   { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓${NC}  $1"; }
info() { echo -e "${CYAN}[$(date '+%H:%M:%S')] ℹ${NC}  $1"; }

SKIP_BACKUP=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --skip-backup) SKIP_BACKUP=true ;;
    --dry-run)     DRY_RUN=true ;;
  esac
done

run_or_dry() {
  if [ "$DRY_RUN" = true ]; then
    info "[DRY RUN] $*"
  else
    "$@"
  fi
}

# Validate Azure login
if ! az account show > /dev/null 2>&1; then
  err "Not logged into Azure. Run: az login"
  exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              CDP TEARDOWN (cost-saving mode)                ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  This will stop compute resources to save ~€170-340/month   ║"
echo "║  Data is preserved. Use cdp-up.sh to restore.              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

#===============================================================================
# Phase 1: Backup
#===============================================================================
if [ "$SKIP_BACKUP" = false ]; then
  log "═══ Phase 1: Backing Up Data ═══"
  mkdir -p "$BACKUP_DIR"

  # PostgreSQL backup
  log "Backing up PostgreSQL..."
  PG_STATE=$(az postgres flexible-server show -g "$RESOURCE_GROUP" -n "$POSTGRES_SERVER" --query "state" -o tsv 2>/dev/null || echo "unknown")
  if [ "$PG_STATE" = "Ready" ]; then
    PGDUMP_FILE="$BACKUP_DIR/pg_dump_${TIMESTAMP}.dump"
    if command -v pg_dump &>/dev/null; then
      info "Running pg_dump (this may take a few minutes for ~2GB)..."
      run_or_dry pg_dump -Fc \
        -h "${POSTGRES_SERVER}.postgres.database.azure.com" \
        -U cdpadmin \
        -d cdp_merged \
        -f "$PGDUMP_FILE" 2>/dev/null && \
        ok "PostgreSQL backup saved: $PGDUMP_FILE" || \
        warn "pg_dump failed - ensure PGPASSWORD is set and firewall allows your IP"
    else
      warn "pg_dump not installed. Skipping PostgreSQL local backup."
      warn "Azure native backup (7-day retention) is still active."
    fi
  else
    warn "PostgreSQL is not running (state: $PG_STATE). Skipping backup."
  fi

  # Tracardi MySQL backup via SSH
  TRACARDI_IP=$(az vm show -d -g "$RESOURCE_GROUP" -n "$TRACARDI_VM" --query "publicIps" -o tsv 2>/dev/null || echo "")
  if [ -n "$TRACARDI_IP" ] && [ "$TRACARDI_IP" != "None" ]; then
    log "Backing up Tracardi MySQL via SSH..."
    MYSQL_FILE="$BACKUP_DIR/tracardi_mysql_${TIMESTAMP}.sql.gz"
    run_or_dry ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "azureuser@$TRACARDI_IP" \
      "docker exec tracardi_mysql mysqldump --all-databases -u root -p\$(docker exec tracardi_mysql printenv MYSQL_ROOT_PASSWORD 2>/dev/null) 2>/dev/null | gzip" \
      > "$MYSQL_FILE" 2>/dev/null && \
      ok "MySQL backup saved: $MYSQL_FILE" || \
      warn "MySQL backup failed (VM may already be stopped)"
  else
    warn "Tracardi VM has no public IP or is stopped. Skipping MySQL backup."
  fi

  # Record backup info
  cat > "$BACKUP_DIR/LAST_BACKUP.txt" <<EOF
timestamp: $TIMESTAMP
pg_dump: ${PGDUMP_FILE:-skipped}
mysql: ${MYSQL_FILE:-skipped}
azure_pg_native_backup: enabled (7-day retention)
EOF
  ok "Backup info written to $BACKUP_DIR/LAST_BACKUP.txt"
else
  warn "Skipping backups (--skip-backup flag)"
fi

#===============================================================================
# Phase 2: Stop Compute Resources
#===============================================================================
log "═══ Phase 2: Stopping Compute ═══"

# Scale Container App to 0
log "Scaling Container App to zero..."
run_or_dry az containerapp update \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --min-replicas 0 \
  --output none 2>/dev/null
ok "Container App scaled to zero"

# Deallocate VMs (preserves disks and data)
log "Deallocating Tracardi VM..."
run_or_dry az vm deallocate \
  --name "$TRACARDI_VM" \
  --resource-group "$RESOURCE_GROUP" \
  --no-wait \
  --output none 2>/dev/null
ok "Tracardi VM deallocation started"

log "Deallocating Data VM..."
run_or_dry az vm deallocate \
  --name "$DATA_VM" \
  --resource-group "$RESOURCE_GROUP" \
  --no-wait \
  --output none 2>/dev/null
ok "Data VM deallocation started"

# Stop PostgreSQL Flexible Server
log "Stopping PostgreSQL Flexible Server..."
run_or_dry az postgres flexible-server stop \
  --resource-group "$RESOURCE_GROUP" \
  --name "$POSTGRES_SERVER" \
  --no-wait 2>/dev/null
ok "PostgreSQL stop initiated"

#===============================================================================
# Phase 3: Summary
#===============================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    TEARDOWN COMPLETE                        ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Stopped:                                                   ║"
echo "║    • Container App (scaled to 0)                            ║"
echo "║    • Tracardi VM (deallocating)                              ║"
echo "║    • Data VM (deallocating)                                  ║"
echo "║    • PostgreSQL Server (stopping)                            ║"
echo "║                                                              ║"
echo "║  Estimated monthly cost while down: ~€15-30                  ║"
echo "║  (storage accounts + Log Analytics only)                     ║"
echo "║                                                              ║"
echo "║  To bring everything back:                                   ║"
echo "║    bash infra/scripts/cdp-up.sh                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Backup location: $BACKUP_DIR"
echo "  Teardown time:   $(date)"
echo ""

# Record state
echo "$TIMESTAMP" > "$BACKUP_DIR/.last_teardown"
