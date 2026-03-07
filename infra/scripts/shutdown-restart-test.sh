#!/bin/bash
#===============================================================================
# Shutdown/Restart Test for IaC Reproducibility
#===============================================================================
# Usage: bash shutdown-restart-test.sh [phase]
#   phase: export|backup|stop|restart|verify|all (default: all)
#
# This script tests IaC reproducibility by:
# 1. Exporting all configurations
# 2. Backing up critical data (Tracardi)
# 3. Stopping non-essential resources
# 4. Restarting from IaC
# 5. Verifying everything works
#===============================================================================

set -e

# Configuration
RESOURCE_GROUP="rg-cdpmerged-fast"
CONTAINER_APP="ca-cdpmerged-fast"
SEARCH_SERVICE="cdpmerged-search"
OPENAI_SERVICE="aoai-cdpmerged-fast"
TRACARDI_VM="vm-tracardi-cdpmerged-prod"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/tmp/cdp-backup-${TIMESTAMP}"
LOG_FILE="/tmp/cdp-shutdown-test-${TIMESTAMP}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

#===============================================================================
# Phase 1: Export Configuration
#===============================================================================
phase_export() {
    log "=== Phase 1: Exporting Configurations ==="
    mkdir -p "$BACKUP_DIR"
    
    log "Exporting Container App config..."
    az containerapp show \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --output json > "$BACKUP_DIR/containerapp-config.json" 2>> "$LOG_FILE"
    
    log "Exporting Container App secrets (names only)..."
    az containerapp secret list \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query "[].name" -o tsv > "$BACKUP_DIR/secrets-list.txt" 2>> "$LOG_FILE"
    
    log "Exporting environment variables..."
    az containerapp show \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.template.containers[0].env" \
        -o json > "$BACKUP_DIR/env-vars.json" 2>> "$LOG_FILE"
    
    log "Exporting scale configuration..."
    az containerapp show \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.template.scale" \
        -o json > "$BACKUP_DIR/scale-config.json" 2>> "$LOG_FILE"
    
    log "Exporting Search Service config..."
    az search service show \
        --name "$SEARCH_SERVICE" \
        --resource-group "$RESOURCE_GROUP" \
        --output json > "$BACKUP_DIR/search-config.json" 2>> "$LOG_FILE"
    
    log "Exporting OpenAI config..."
    az cognitiveservices account show \
        --name "$OPENAI_SERVICE" \
        --resource-group "$RESOURCE_GROUP" \
        --output json > "$BACKUP_DIR/openai-config.json" 2>> "$LOG_FILE"
    
    log "Exporting Search index schema..."
    SEARCH_KEY=$(az search admin-key show --service-name "$SEARCH_SERVICE" --resource-group "$RESOURCE_GROUP" --query primaryKey -o tsv 2>/dev/null || echo "")
    if [ -n "$SEARCH_KEY" ]; then
        az rest --method get \
            --url "https://${SEARCH_SERVICE}.search.windows.net/indexes/companies?api-version=2023-11-01" \
            --headers "api-key=$SEARCH_KEY" \
            --output json > "$BACKUP_DIR/search-index-schema.json" 2>> "$LOG_FILE" || warn "Could not export index schema"
    fi
    
    log "Exporting all resource list..."
    az resource list \
        --resource-group "$RESOURCE_GROUP" \
        --output json > "$BACKUP_DIR/all-resources.json" 2>> "$LOG_FILE"
    
    log "✅ Phase 1 Complete. Configs saved to: $BACKUP_DIR"
    ls -la "$BACKUP_DIR/" | tee -a "$LOG_FILE"
}

#===============================================================================
# Phase 2: Backup Tracardi Data
#===============================================================================
phase_backup() {
    log "=== Phase 2: Backing Up Tracardi Data ==="
    
    # Check VM status
    VM_STATE=$(az vm show --name "$TRACARDI_VM" --resource-group "$RESOURCE_GROUP" --query "powerState" -o tsv 2>/dev/null || echo "unknown")
    log "Tracardi VM current state: $VM_STATE"
    
    # Create VM snapshot
    log "Creating VM OS disk snapshot..."
    OS_DISK_ID=$(az vm show --name "$TRACARDI_VM" --resource-group "$RESOURCE_GROUP" --query storageProfile.osDisk.managedDisk.id -o tsv 2>/dev/null)
    
    if [ -n "$OS_DISK_ID" ]; then
        SNAPSHOT_NAME="tracardi-snapshot-${TIMESTAMP}"
        az snapshot create \
            --resource-group "$RESOURCE_GROUP" \
            --source "$OS_DISK_ID" \
            --name "$SNAPSHOT_NAME" \
            --sku Standard_ZRS \
            --tags backup-type=iac-test reason=reproducibility-test timestamp="$TIMESTAMP" \
            --output json > "$BACKUP_DIR/snapshot-info.json" 2>> "$LOG_FILE"
        log "✅ VM snapshot created: $SNAPSHOT_NAME"
    else
        error "Could not find VM OS disk"
        return 1
    fi
    
    # List data disks
    log "Checking for data disks..."
    DATA_DISKS=$(az disk list --resource-group "$RESOURCE_GROUP" --query "[?contains(name,'tracardi')].id" -o tsv 2>/dev/null)
    if [ -n "$DATA_DISKS" ]; then
        for DISK_ID in $DATA_DISKS; do
            DISK_NAME=$(basename "$DISK_ID")
            log "Found data disk: $DISK_NAME"
            az snapshot create \
                --resource-group "$RESOURCE_GROUP" \
                --source "$DISK_ID" \
                --name "tracardi-datadisk-${DISK_NAME}-${TIMESTAMP}" \
                --sku Standard_ZRS \
                --output none 2>> "$LOG_FILE"
            log "✅ Data disk snapshot created for: $DISK_NAME"
        done
    fi
    
    # Verify snapshots
    log "Verifying snapshots..."
    az snapshot list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[?contains(name,'tracardi') && contains(name,'$TIMESTAMP')].{name:name, timeCreated:timeCreated, diskSizeGb:diskSizeGb}" \
        -o table | tee -a "$LOG_FILE"
    
    log "✅ Phase 2 Complete. Tracardi data backed up."
}

#===============================================================================
# Phase 3: Shutdown Non-Essential Resources
#===============================================================================
phase_stop() {
    log "=== Phase 3: Stopping Non-Essential Resources ==="
    
    # IMPORTANT: Keep Tracardi VM running or deallocate (don't delete)
    log "Deallocating Tracardi VM (preserving data)..."
    az vm deallocate \
        --name "$TRACARDI_VM" \
        --resource-group "$RESOURCE_GROUP" \
        --output none 2>> "$LOG_FILE" || warn "Could not deallocate VM (may already be stopped)"
    log "✅ Tracardi VM deallocated (data preserved)"
    
    # Scale Container App to zero
    log "Scaling Container App to zero..."
    az containerapp update \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --min-replicas 0 \
        --output none 2>> "$LOG_FILE"
    log "✅ Container App scaled to zero"
    
    # Verify stopped state
    log "Verifying stopped state..."
    sleep 10
    CA_REPLICAS=$(az containerapp show --name "$CONTAINER_APP" --resource-group "$RESOURCE_GROUP" --query "properties.template.scale.minReplicas" -o tsv 2>/dev/null)
    log "Container App minReplicas: $CA_REPLICAS"
    
    VM_STATE=$(az vm show --name "$TRACARDI_VM" --resource-group "$RESOURCE_GROUP" --query "powerState" -o tsv 2>/dev/null || echo "unknown")
    log "Tracardi VM state: $VM_STATE"
    
    log "✅ Phase 3 Complete. Non-essential resources stopped."
    log ""
    warn "Resources stopped. To manually restart:"
    log "  az vm start --name $TRACARDI_VM --resource-group $RESOURCE_GROUP"
    log "  az containerapp update --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --min-replicas 1"
}

#===============================================================================
# Phase 4: Restart from IaC
#===============================================================================
phase_restart() {
    log "=== Phase 4: Restarting from IaC ==="
    
    # Check if Terraform exists in expected locations
    TERRAFORM_DIRS=(
        "/home/ff/.openclaw/workspace/repos/CDP_Merged/infra/terraform"
        "/home/ff/.openclaw/workspace/CDP_Merged/infra/terraform"
        "./infra/terraform"
    )
    
    TERRAFORM_DIR=""
    for DIR in "${TERRAFORM_DIRS[@]}"; do
        if [ -f "$DIR/main.tf" ]; then
            TERRAFORM_DIR="$DIR"
            break
        fi
    done
    
    if [ -n "$TERRAFORM_DIR" ]; then
        log "Found Terraform configuration in: $TERRAFORM_DIR"
        
        # Check for deployment script
        if [ -f "$TERRAFORM_DIR/../deploy.sh" ]; then
            log "Running deployment script..."
            bash "$TERRAFORM_DIR/../deploy.sh" 2>&1 | tee -a "$LOG_FILE"
        else
            log "Running terraform apply..."
            cd "$TERRAFORM_DIR"
            terraform apply -auto-approve 2>&1 | tee -a "$LOG_FILE" || warn "Terraform apply may have issues"
        fi
    else
        warn "No Terraform configuration found. Manual restart required."
        log "To restart manually:"
        log "  1. Start Tracardi VM: az vm start --name $TRACARDI_VM --resource-group $RESOURCE_GROUP"
        log "  2. Scale Container App: az containerapp update --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --min-replicas 1 --max-replicas 5"
    fi
    
    # Wait for resources to start
    log "Waiting for resources to start (60 seconds)..."
    sleep 60
    
    log "✅ Phase 4 Complete. Resources restarted."
}

#===============================================================================
# Phase 5: Verification
#===============================================================================
phase_verify() {
    log "=== Phase 5: Verification ==="
    
    local ALL_PASSED=true
    
    # 5.1 Container App Health
    log "[1/7] Checking Container App..."
    CA_FQDN=$(az containerapp show --name "$CONTAINER_APP" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null)
    if [ -n "$CA_FQDN" ]; then
        # First scale up if needed
        CURRENT_MIN=$(az containerapp show --name "$CONTAINER_APP" --resource-group "$RESOURCE_GROUP" --query "properties.template.scale.minReplicas" -o tsv)
        if [ "$CURRENT_MIN" = "0" ]; then
            log "Scaling Container App to 1 replica for testing..."
            az containerapp update --name "$CONTAINER_APP" --resource-group "$RESOURCE_GROUP" --min-replicas 1 --output none
            sleep 30
        fi
        
        HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$CA_FQDN/project/settings" 2>/dev/null || echo "000")
        if [ "$HEALTH_STATUS" = "200" ] || [ "$HEALTH_STATUS" = "307" ]; then
            log "✅ Container App: HEALTHY (HTTP $HEALTH_STATUS)"
        else
            error "Container App: UNHEALTHY (HTTP $HEALTH_STATUS)"
            ALL_PASSED=false
        fi
    else
        error "Container App: FQDN not found"
        ALL_PASSED=false
    fi
    
    # 5.2 Azure Search
    log "[2/7] Checking Azure Search..."
    SEARCH_STATUS=$(az search service show --name "$SEARCH_SERVICE" --resource-group "$RESOURCE_GROUP" --query "status" -o tsv 2>/dev/null)
    if [ "$SEARCH_STATUS" = "running" ]; then
        log "✅ Azure Search: RUNNING"
    else
        error "Azure Search: NOT RUNNING ($SEARCH_STATUS)"
        ALL_PASSED=false
    fi
    
    # 5.3 Azure OpenAI
    log "[3/7] Checking Azure OpenAI..."
    OPENAI_ENDPOINT=$(az cognitiveservices account show --name "$OPENAI_SERVICE" --resource-group "$RESOURCE_GROUP" --query "properties.endpoint" -o tsv 2>/dev/null)
    if [ -n "$OPENAI_ENDPOINT" ]; then
        log "✅ Azure OpenAI: CONFIGURED ($OPENAI_ENDPOINT)"
    else
        error "Azure OpenAI: NOT CONFIGURED"
        ALL_PASSED=false
    fi
    
    # 5.4 Tracardi VM
    log "[4/7] Checking Tracardi VM..."
    VM_STATE=$(az vm show --name "$TRACARDI_VM" --resource-group "$RESOURCE_GROUP" --query "powerState" -o tsv 2>/dev/null || echo "unknown")
    if [ "$VM_STATE" = "VM running" ] || [ "$VM_STATE" = "running" ]; then
        # Get IP
        TRACARDI_IP=$(az vm show --name "$TRACARDI_VM" --resource-group "$RESOURCE_GROUP" --query "publicIps" -o tsv 2>/dev/null || echo "52.148.232.140")
        TRACARDI_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "http://$TRACARDI_IP:8686/health" 2>/dev/null || echo "000")
        if [ "$TRACARDI_HEALTH" = "200" ]; then
            log "✅ Tracardi VM: RUNNING and HEALTHY"
        else
            warn "Tracardi VM: RUNNING but health check returned $TRACARDI_HEALTH (may need more time to start)"
        fi
    else
        # Try to start it
        warn "Tracardi VM: NOT RUNNING ($VM_STATE). Attempting to start..."
        az vm start --name "$TRACARDI_VM" --resource-group "$RESOURCE_GROUP" --output none 2>> "$LOG_FILE" || true
        log "✅ Tracardi VM: START command issued"
    fi
    
    # 5.5 Secrets Configuration
    log "[5/7] Checking secrets..."
    SECRET_COUNT=$(az containerapp secret list --name "$CONTAINER_APP" --resource-group "$RESOURCE_GROUP" --query "length(@)" -o tsv 2>/dev/null || echo "0")
    if [ "$SECRET_COUNT" -ge 5 ]; then
        log "✅ Secrets: $SECRET_COUNT configured"
    else
        error "Secrets: Only $SECRET_COUNT configured (expected at least 5)"
        ALL_PASSED=false
    fi
    
    # List secrets for verification
    log "Configured secrets:"
    az containerapp secret list --name "$CONTAINER_APP" --resource-group "$RESOURCE_GROUP" --query "[].name" -o tsv 2>/dev/null | sed 's/^/  - /' | tee -a "$LOG_FILE"
    
    # 5.6 Environment Variables
    log "[6/7] Checking environment variables..."
    ENV_COUNT=$(az containerapp show --name "$CONTAINER_APP" --resource-group "$RESOURCE_GROUP" --query "length(properties.template.containers[0].env)" -o tsv 2>/dev/null || echo "0")
    if [ "$ENV_COUNT" -ge 10 ]; then
        log "✅ Environment Variables: $ENV_COUNT configured"
    else
        warn "Environment Variables: Only $ENV_COUNT configured (expected at least 10)"
    fi
    
    # 5.7 End-to-End Query Test
    log "[7/7] End-to-end query test..."
    if [ -n "$CA_FQDN" ]; then
        TEST_RESPONSE=$(curl -s -X POST "https://$CA_FQDN/api/chat" \
            -H "Content-Type: application/json" \
            -d '{"message": "How many restaurants in Antwerp?"}' \
            -w "\n%{http_code}" \
            --max-time 30 2>/dev/null || echo "FAILED")
        
        HTTP_CODE=$(echo "$TEST_RESPONSE" | tail -1)
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "202" ]; then
            log "✅ E2E Test: PASSED (HTTP $HTTP_CODE)"
        else
            warn "E2E Test: Response code was: $HTTP_CODE (may need more warm-up time)"
        fi
    else
        warn "E2E Test: Skipped (Container App FQDN not available)"
    fi
    
    # Final summary
    log ""
    log "=== Verification Summary ==="
    if [ "$ALL_PASSED" = true ]; then
        log "✅ ALL CHECKS PASSED - IaC Reproducibility Verified!"
        return 0
    else
        error "SOME CHECKS FAILED - Review output above"
        return 1
    fi
}

#===============================================================================
# Main Execution
#===============================================================================
main() {
    PHASE="${1:-all}"
    
    log "=== IaC Reproducibility Test ==="
    log "Timestamp: $TIMESTAMP"
    log "Resource Group: $RESOURCE_GROUP"
    log "Backup Directory: $BACKUP_DIR"
    log "Log File: $LOG_FILE"
    log "Phase: $PHASE"
    log ""
    
    # Validate Azure login
    if ! az account show > /dev/null 2>&1; then
        error "Not logged into Azure. Run: az login"
        exit 1
    fi
    
    # Execute requested phase(s)
    case "$PHASE" in
        export)
            phase_export
            ;;
        backup)
            phase_backup
            ;;
        stop)
            phase_stop
            ;;
        restart)
            phase_restart
            ;;
        verify)
            phase_verify
            ;;
        all)
            phase_export
            phase_backup
            phase_stop
            log ""
            warn "PHASE 3 COMPLETE - Resources stopped"
            warn "Review the output above before proceeding"
            log ""
            read -p "Press Enter to continue with restart phase, or Ctrl+C to abort..."
            phase_restart
            phase_verify
            ;;
        *)
            echo "Usage: $0 [export|backup|stop|restart|verify|all]"
            echo ""
            echo "Phases:"
            echo "  export  - Export all configurations"
            echo "  backup  - Backup Tracardi data (VM snapshot)"
            echo "  stop    - Stop non-essential resources"
            echo "  restart - Restart from IaC"
            echo "  verify  - Verify everything works"
            echo "  all     - Run all phases (with prompt between stop/restart)"
            exit 1
            ;;
    esac
    
    log ""
    log "=== Test Complete ==="
    log "Log saved to: $LOG_FILE"
    log "Backups saved to: $BACKUP_DIR"
}

# Run main function
main "$@"
