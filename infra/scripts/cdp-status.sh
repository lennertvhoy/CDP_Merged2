#!/bin/bash
#===============================================================================
# CDP Status - Resource & Cost Overview
#===============================================================================
# Shows running state, health, and estimated cost for all CDP resources.
#
# Usage: bash cdp-status.sh
#===============================================================================

set -euo pipefail

RESOURCE_GROUP="rg-cdpmerged-fast"
POSTGRES_SERVER="cdp-postgres-661"
TRACARDI_VM="vm-tracardi-cdpmerged-prod"
DATA_VM="vm-data-cdpmerged-prod"
CONTAINER_APP="ca-cdpmerged-fast"
OPENAI_SERVICE="aoai-cdpmerged-fast"
BACKUP_DIR="${CDP_BACKUP_DIR:-$HOME/cdp-backups}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Validate Azure login
if ! az account show > /dev/null 2>&1; then
  echo -e "${RED}Not logged into Azure. Run: az login${NC}"
  exit 1
fi

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║              CDP Infrastructure Status                      ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║  $(date)                       ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

TOTAL_MONTHLY=0

#--- PostgreSQL ---
PG_STATE=$(az postgres flexible-server show -g "$RESOURCE_GROUP" -n "$POSTGRES_SERVER" \
  --query "state" -o tsv 2>/dev/null || echo "NOT FOUND")
PG_SKU=$(az postgres flexible-server show -g "$RESOURCE_GROUP" -n "$POSTGRES_SERVER" \
  --query "sku.name" -o tsv 2>/dev/null || echo "?")
if [ "$PG_STATE" = "Ready" ]; then
  echo -e "  ${GREEN}●${NC} PostgreSQL ($POSTGRES_SERVER)     ${GREEN}RUNNING${NC}  [$PG_SKU]  ~€25-35/mo"
  TOTAL_MONTHLY=$((TOTAL_MONTHLY + 30))
elif [ "$PG_STATE" = "Stopped" ]; then
  echo -e "  ${RED}○${NC} PostgreSQL ($POSTGRES_SERVER)     ${RED}STOPPED${NC}  [$PG_SKU]  ~€5/mo (storage only)"
  TOTAL_MONTHLY=$((TOTAL_MONTHLY + 5))
else
  echo -e "  ${YELLOW}?${NC} PostgreSQL ($POSTGRES_SERVER)     ${YELLOW}$PG_STATE${NC}"
fi

#--- Data VM ---
DATA_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$DATA_VM" \
  --query "instanceView.statuses[?starts_with(code,'PowerState')].displayStatus" -o tsv 2>/dev/null || echo "NOT FOUND")
DATA_SIZE=$(az vm show -g "$RESOURCE_GROUP" -n "$DATA_VM" --query "hardwareProfile.vmSize" -o tsv 2>/dev/null || echo "?")
if [ "$DATA_STATE" = "VM running" ]; then
  echo -e "  ${GREEN}●${NC} Data VM ($DATA_VM)         ${GREEN}RUNNING${NC}  [$DATA_SIZE]  ~€15-18/mo"
  TOTAL_MONTHLY=$((TOTAL_MONTHLY + 17))
elif [ "$DATA_STATE" = "VM deallocated" ]; then
  echo -e "  ${RED}○${NC} Data VM ($DATA_VM)         ${RED}DEALLOCATED${NC}  ~€1/mo (disk only)"
  TOTAL_MONTHLY=$((TOTAL_MONTHLY + 1))
else
  echo -e "  ${YELLOW}?${NC} Data VM ($DATA_VM)         ${YELLOW}$DATA_STATE${NC}"
fi

#--- Tracardi VM ---
TRACARDI_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$TRACARDI_VM" \
  --query "instanceView.statuses[?starts_with(code,'PowerState')].displayStatus" -o tsv 2>/dev/null || echo "NOT FOUND")
TRACARDI_SIZE=$(az vm show -g "$RESOURCE_GROUP" -n "$TRACARDI_VM" --query "hardwareProfile.vmSize" -o tsv 2>/dev/null || echo "?")
if [ "$TRACARDI_STATE" = "VM running" ]; then
  echo -e "  ${GREEN}●${NC} Tracardi VM ($TRACARDI_VM)  ${GREEN}RUNNING${NC}  [$TRACARDI_SIZE]  ~€35-40/mo"
  TOTAL_MONTHLY=$((TOTAL_MONTHLY + 38))
elif [ "$TRACARDI_STATE" = "VM deallocated" ]; then
  echo -e "  ${RED}○${NC} Tracardi VM ($TRACARDI_VM)  ${RED}DEALLOCATED${NC}  ~€1/mo (disk only)"
  TOTAL_MONTHLY=$((TOTAL_MONTHLY + 1))
else
  echo -e "  ${YELLOW}?${NC} Tracardi VM ($TRACARDI_VM)  ${YELLOW}$TRACARDI_STATE${NC}"
fi

#--- Container App ---
CA_REPLICAS=$(az containerapp show -n "$CONTAINER_APP" -g "$RESOURCE_GROUP" \
  --query "properties.template.scale.minReplicas" -o tsv 2>/dev/null || echo "?")
CA_FQDN=$(az containerapp show -n "$CONTAINER_APP" -g "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null || echo "?")
if [ "$CA_REPLICAS" = "0" ]; then
  echo -e "  ${YELLOW}○${NC} Container App ($CONTAINER_APP)     ${YELLOW}SCALE-TO-ZERO${NC}  ~€5/mo (env only)"
  TOTAL_MONTHLY=$((TOTAL_MONTHLY + 5))
else
  echo -e "  ${GREEN}●${NC} Container App ($CONTAINER_APP)     ${GREEN}ACTIVE${NC} (min=$CA_REPLICAS)  ~€15-25/mo"
  TOTAL_MONTHLY=$((TOTAL_MONTHLY + 20))
fi

#--- OpenAI ---
OPENAI_ENDPOINT=$(az cognitiveservices account show -n "$OPENAI_SERVICE" -g "$RESOURCE_GROUP" \
  --query "properties.endpoint" -o tsv 2>/dev/null || echo "NOT FOUND")
if [ -n "$OPENAI_ENDPOINT" ] && [ "$OPENAI_ENDPOINT" != "NOT FOUND" ]; then
  echo -e "  ${GREEN}●${NC} Azure OpenAI ($OPENAI_SERVICE)       ${GREEN}ACTIVE${NC}  ~€0-5/mo (pay-per-use)"
  TOTAL_MONTHLY=$((TOTAL_MONTHLY + 3))
fi

#--- Fixed costs ---
echo -e "  ${CYAN}≋${NC} Storage accounts (3x)                  ${CYAN}ALWAYS ON${NC}  ~€3-5/mo"
TOTAL_MONTHLY=$((TOTAL_MONTHLY + 4))
echo -e "  ${CYAN}≋${NC} Log Analytics workspace                 ${CYAN}ALWAYS ON${NC}  ~€15-25/mo"
TOTAL_MONTHLY=$((TOTAL_MONTHLY + 20))

echo ""
echo -e "  ${BOLD}───────────────────────────────────────────────────${NC}"
echo -e "  ${BOLD}Estimated monthly total: ~€${TOTAL_MONTHLY}/month${NC}"
echo -e "  ${BOLD}Target budget:           €150/month${NC}"
if [ "$TOTAL_MONTHLY" -le 150 ]; then
  echo -e "  ${GREEN}✓ Within budget${NC}"
else
  echo -e "  ${RED}✗ Over budget by ~€$((TOTAL_MONTHLY - 150))/month${NC}"
fi

#--- Last backup ---
echo ""
if [ -f "$BACKUP_DIR/LAST_BACKUP.txt" ]; then
  echo -e "  ${BOLD}Last backup:${NC}"
  sed 's/^/    /' "$BACKUP_DIR/LAST_BACKUP.txt"
elif [ -f "$BACKUP_DIR/.last_teardown" ]; then
  echo -e "  ${BOLD}Last teardown:${NC} $(cat "$BACKUP_DIR/.last_teardown")"
else
  echo -e "  ${YELLOW}No backup records found in $BACKUP_DIR${NC}"
fi

echo ""
echo -e "  ${CYAN}Commands:${NC}"
echo "    bash infra/scripts/cdp-down.sh    # Teardown (save costs)"
echo "    bash infra/scripts/cdp-up.sh      # Bring back online"
echo "    bash infra/scripts/cdp-status.sh  # This status check"
echo ""
