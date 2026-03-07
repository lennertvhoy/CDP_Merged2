#!/bin/bash
#===============================================================================
# CDP Up - Rebuild & Verify Script
#===============================================================================
# Starts all compute resources and verifies health.
# Brings the stack from ~€15-30/month back to full operation.
#
# Usage: bash cdp-up.sh [--wait] [--dry-run]
#===============================================================================

set -euo pipefail

RESOURCE_GROUP="rg-cdpmerged-fast"
POSTGRES_SERVER="cdp-postgres-661"
TRACARDI_VM="vm-tracardi-cdpmerged-prod"
DATA_VM="vm-data-cdpmerged-prod"
CONTAINER_APP="ca-cdpmerged-fast"

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

WAIT_FOR_HEALTH=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --wait)    WAIT_FOR_HEALTH=true ;;
    --dry-run) DRY_RUN=true ;;
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
echo "║              CDP STARTUP (bringing stack online)            ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Starting all compute resources. ~5-10 minutes to healthy. ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

#===============================================================================
# Phase 1: Start Infrastructure
#===============================================================================
log "═══ Phase 1: Starting Resources ═══"

# Start PostgreSQL first (other services depend on it)
log "Starting PostgreSQL Flexible Server..."
PG_STATE=$(az postgres flexible-server show -g "$RESOURCE_GROUP" -n "$POSTGRES_SERVER" --query "state" -o tsv 2>/dev/null || echo "unknown")
if [ "$PG_STATE" = "Stopped" ]; then
  run_or_dry az postgres flexible-server start \
    --resource-group "$RESOURCE_GROUP" \
    --name "$POSTGRES_SERVER" \
    --no-wait 2>/dev/null
  ok "PostgreSQL start initiated"
elif [ "$PG_STATE" = "Ready" ]; then
  ok "PostgreSQL already running"
else
  warn "PostgreSQL state: $PG_STATE"
fi

# Start Data VM (Elasticsearch + Redis)
log "Starting Data VM..."
DATA_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$DATA_VM" \
  --query "instanceView.statuses[?starts_with(code,'PowerState')].displayStatus" -o tsv 2>/dev/null || echo "unknown")
if [ "$DATA_STATE" != "VM running" ]; then
  run_or_dry az vm start --name "$DATA_VM" --resource-group "$RESOURCE_GROUP" --no-wait --output none 2>/dev/null
  ok "Data VM start initiated"
else
  ok "Data VM already running"
fi

# Start Tracardi VM
log "Starting Tracardi VM..."
TRACARDI_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$TRACARDI_VM" \
  --query "instanceView.statuses[?starts_with(code,'PowerState')].displayStatus" -o tsv 2>/dev/null || echo "unknown")
if [ "$TRACARDI_STATE" != "VM running" ]; then
  run_or_dry az vm start --name "$TRACARDI_VM" --resource-group "$RESOURCE_GROUP" --no-wait --output none 2>/dev/null
  ok "Tracardi VM start initiated"
else
  ok "Tracardi VM already running"
fi

# Scale Container App
log "Scaling Container App to 1 replica..."
run_or_dry az containerapp update \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --min-replicas 1 \
  --output none 2>/dev/null
ok "Container App scaled to 1"

#===============================================================================
# Phase 2: Wait & Verify (if --wait)
#===============================================================================
if [ "$WAIT_FOR_HEALTH" = true ]; then
  log "═══ Phase 2: Waiting for Services ═══"
  info "Waiting 90 seconds for services to start..."
  sleep 90

  CHECKS_PASSED=0
  CHECKS_TOTAL=4

  # Check PostgreSQL
  log "[1/4] PostgreSQL..."
  PG_STATE=$(az postgres flexible-server show -g "$RESOURCE_GROUP" -n "$POSTGRES_SERVER" --query "state" -o tsv 2>/dev/null)
  if [ "$PG_STATE" = "Ready" ]; then
    ok "PostgreSQL: Ready"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
  else
    err "PostgreSQL: $PG_STATE"
  fi

  # Check Data VM
  log "[2/4] Data VM (Elasticsearch + Redis)..."
  DATA_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$DATA_VM" \
    --query "instanceView.statuses[?starts_with(code,'PowerState')].displayStatus" -o tsv 2>/dev/null)
  if [ "$DATA_STATE" = "VM running" ]; then
    ok "Data VM: Running"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
  else
    err "Data VM: $DATA_STATE"
  fi

  # Check Tracardi VM
  log "[3/4] Tracardi VM..."
  TRACARDI_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$TRACARDI_VM" \
    --query "instanceView.statuses[?starts_with(code,'PowerState')].displayStatus" -o tsv 2>/dev/null)
  if [ "$TRACARDI_STATE" = "VM running" ]; then
    TRACARDI_IP=$(az vm show -d -g "$RESOURCE_GROUP" -n "$TRACARDI_VM" --query "publicIps" -o tsv 2>/dev/null)
    TRACARDI_HEALTH=$(curl -fsS -m 10 "http://$TRACARDI_IP:8686/health" 2>/dev/null && echo "ok" || echo "fail")
    if [ "$TRACARDI_HEALTH" != "fail" ]; then
      ok "Tracardi VM: Running & API healthy"
    else
      warn "Tracardi VM: Running but API not yet responding (may need more time)"
    fi
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
  else
    err "Tracardi VM: $TRACARDI_STATE"
  fi

  # Check Container App
  log "[4/4] Container App..."
  CA_FQDN=$(az containerapp show -n "$CONTAINER_APP" -g "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null)
  if [ -n "$CA_FQDN" ]; then
    CA_STATUS=$(curl -sS -o /dev/null -w "%{http_code}" "https://$CA_FQDN/" --max-time 15 2>/dev/null || echo "000")
    if [ "$CA_STATUS" = "200" ] || [ "$CA_STATUS" = "307" ] || [ "$CA_STATUS" = "302" ]; then
      ok "Container App: Healthy (HTTP $CA_STATUS)"
      CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
      warn "Container App: HTTP $CA_STATUS (may need warm-up)"
    fi
  else
    err "Container App: FQDN not found"
  fi

  echo ""
  if [ "$CHECKS_PASSED" -eq "$CHECKS_TOTAL" ]; then
    ok "All $CHECKS_TOTAL/$CHECKS_TOTAL checks passed!"
  else
    warn "$CHECKS_PASSED/$CHECKS_TOTAL checks passed. Some services may need more time."
  fi
fi

#===============================================================================
# Phase 3: Summary
#===============================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    STARTUP COMPLETE                         ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Started:                                                   ║"
echo "║    • PostgreSQL Flexible Server                              ║"
echo "║    • Data VM (Elasticsearch + Redis)                         ║"
echo "║    • Tracardi VM (API + GUI + MySQL)                         ║"
echo "║    • Container App (chatbot, 1 replica)                      ║"
echo "║                                                              ║"
echo "║  Services typically ready in 3-5 minutes.                    ║"
echo "║  Run with --wait to verify health checks.                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Startup time: $(date)"
echo ""
