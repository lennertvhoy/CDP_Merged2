#!/usr/bin/env bash
#===============================================================================
# CDP_Merged Quick Cost Optimization Script
# Run this to immediately apply cost-saving changes to the dev environment
#===============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RG="rg-cdpmerged-fast"
APP_NAME="ca-cdpmerged-fast"
SEARCH_NAME="cdpmerged-search"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     CDP_Merged Azure Cost Optimization - Quick Actions       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo

# Check if user is logged in
if ! az account show >/devdev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Not logged into Azure. Running az login...${NC}"
    az login
fi

echo -e "${BLUE}Current subscription:${NC}"
az account show --query "{Name:name, ID:id}" -o table
echo

#===============================================================================
# Function: Optimize Container App
#===============================================================================
optimize_container_app() {
    echo -e "${YELLOW}📦 Optimizing Container App...${NC}"
    
    echo -e "${BLUE}Current configuration:${NC}"
    az containerapp show -n "$APP_NAME" -g "$RG" --query "properties.template.{cpu:containers[0].resources.cpu, memory:containers[0].resources.memory, minReplicas:scale.minReplicas, maxReplicas:scale.maxReplicas}" -o table 2>/dev/null || {
        echo -e "${RED}❌ Could not read Container App configuration${NC}"
        return 1
    }
    
    echo
    echo -e "${YELLOW}Apply dev optimization (0.25 CPU, 0.5Gi, min 0 replicas)? [y/N]${NC}"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Applying cost optimization...${NC}"
        
        # Update Container App
        az containerapp update \
            --name "$APP_NAME" \
            --resource-group "$RG" \
            --cpu 0.25 \
            --memory 0.5Gi \
            --min-replicas 0 \
            --max-replicas 5
        
        echo -e "${GREEN}✅ Container App optimized for dev environment${NC}"
        echo -e "${YELLOW}⚠️  Note: First request after idle will have ~5-10s cold start${NC}"
    else
        echo -e "${YELLOW}⏭️  Skipped Container App optimization${NC}"
    fi
    echo
}

#===============================================================================
# Function: Analyze Log Analytics Workspaces
#===============================================================================
analyze_log_workspaces() {
    echo -e "${YELLOW}📊 Analyzing Log Analytics Workspaces...${NC}"
    
    echo -e "${BLUE}Workspaces found:${NC}"
    az monitor log-analytics workspace list -g "$RG" -o table
    
    workspace_count=$(az monitor log-analytics workspace list -g "$RG" --query "length(@)" -o tsv)
    
    if [ "$workspace_count" -gt 1 ]; then
        echo
        echo -e "${YELLOW}⚠️  Found $workspace_count Log Analytics workspaces!${NC}"
        echo -e "${YELLOW}Consolidating to one workspace can save €20-40/month${NC}"
        echo
        echo -e "${BLUE}Checking recent data ingestion...${NC}"
        
        for ws in $(az monitor log-analytics workspace list -g "$RG" --query "[].name" -o tsv); do
            echo -e "\n${BLUE}Workspace: $ws${NC}"
            # Try to get recent usage stats
            az monitor log-analytics workspace show --name "$ws" --resource-group "$RG" --query "{Name:name, SKU:sku.name, Retention:retentionInDays, Created:createdDate}" -o table
        done
        
        echo
        echo -e "${YELLOW}⚠️  Manual review required:${NC}"
        echo -e "Check which workspace is linked to your Container App and Application Insights"
        echo -e "before deleting. This is typically: workspace-rgcdpmergedfastF2eP"
        echo
    else
        echo -e "${GREEN}✅ Only one Log Analytics workspace found - good!${NC}"
    fi
    echo
}

#===============================================================================
# Function: Check Azure Search Tier
#===============================================================================
check_search_tier() {
    echo -e "${YELLOW}🔍 Checking Azure AI Search Configuration...${NC}"
    
    az search service show --name "$SEARCH_NAME" --resource-group "$RG" --query "{Name:name, SKU:sku.name, Replicas:replicaCount, Partitions:partitionCount}" -o table 2>/dev/null || {
        echo -e "${RED}❌ Could not read Search service configuration${NC}"
        return 1
    }
    
    sku=$(az search service show --name "$SEARCH_NAME" --resource-group "$RG" --query "sku.name" -o tsv)
    
    if [ "$sku" == "free" ]; then
        echo -e "${GREEN}✅ Already on Free tier (€0/month)${NC}"
    elif [ "$sku" == "basic" ]; then
        echo -e "${YELLOW}ℹ️  Current: Basic tier (~€60/month)${NC}"
        echo -e "${BLUE}For dev: Consider Free tier (50MB limit, 3 indexes max)${NC}"
        
        # Try to get index stats
        echo
        echo -e "${BLUE}Fetching index information...${NC}"
        az search index list --service-name "$SEARCH_NAME" --resource-group "$RG" -o table 2>/dev/null || echo -e "${YELLOW}⚠️  Cannot list indices (may need admin key)${NC}"
    fi
    echo
}

#===============================================================================
# Function: Analyze VMs
#===============================================================================
analyze_vms() {
    echo -e "${YELLOW}🖥️  Analyzing Virtual Machines...${NC}"
    
    az vm list -g "$RG" --query "[].{Name:name, Size:hardwareProfile.vmSize, OS:storageProfile.osDisk.osType}" -o table
    
    echo
    echo -e "${BLUE}Checking VM power states...${NC}"
    for vm in $(az vm list -g "$RG" --query "[].name" -o tsv); do
        state=$(az vm get-instance-view --name "$vm" --resource-group "$RG" --query "instanceView.statuses[?code starts_with(@.code, 'PowerState/')] | [0].displayStatus" -o tsv 2>/dev/null || echo "Unknown")
        echo -e "  $vm: $state"
    done
    
    echo
    echo -e "${YELLOW}⚠️  DO NOT stop Tracardi VM - data ingestion is critical!${NC}"
    echo -e "${BLUE}Data VM can be stopped during off-hours to save ~€12-15/month${NC}"
    echo
}

#===============================================================================
# Function: Cost Estimation
#===============================================================================
estimate_costs() {
    echo -e "${YELLOW}💰 Current Resource Cost Estimation...${NC}"
    echo
    
    # Get resource counts
    container_apps=$(az containerapp list -g "$RG" --query "length(@)" -o tsv)
    vms=$(az vm list -g "$RG" --query "length(@)" -o tsv)
    workspaces=$(az monitor log-analytics workspace list -g "$RG" --query "length(@)" -o tsv)
    
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│ Resource Type          │ Count │ Est. Monthly Cost         │"
    echo "├─────────────────────────────────────────────────────────────┤"
    echo "│ Container Apps         │   $container_apps   │ €35-50                    │"
    echo "│ Virtual Machines       │   $vms   │ €37-45                    │"
    echo "│ Log Analytics          │   $workspaces   │ €$(($workspaces * 10))-60 (varies)     │"
    echo "│ Azure AI Search        │   1   │ €60 (Basic) / €0 (Free)   │"
    echo "│ Container Registry     │   1   │ €4                        │"
    echo "│ Storage/Networking     │   -   │ €15-20                    │"
    echo "├─────────────────────────────────────────────────────────────┤"
    echo "│ TOTAL (approximate)    │       │ €151-229                  │"
    echo "└─────────────────────────────────────────────────────────────┘"
    echo
    echo -e "${GREEN}Potential dev savings with optimizations: €105-135/month (50%)${NC}"
    echo
}

#===============================================================================
# Main Menu
#===============================================================================
show_menu() {
    echo -e "${BLUE}Available Actions:${NC}"
    echo "  1) Optimize Container App (dev specs)"
    echo "  2) Analyze Log Analytics Workspaces"
    echo "  3) Check Azure AI Search Tier"
    echo "  4) Analyze Virtual Machines"
    echo "  5) Show Cost Estimation"
    echo "  6) Run All Analyses"
    echo "  7) Exit"
    echo
    echo -n "Select option [1-7]: "
}

#===============================================================================
# Main
#===============================================================================
main() {
    if [ $# -eq 0 ]; then
        # Interactive mode
        while true; do
            show_menu
            read -r choice
            
            case $choice in
                1) optimize_container_app ;;
                2) analyze_log_workspaces ;;
                3) check_search_tier ;;
                4) analyze_vms ;;
                5) estimate_costs ;;
                6) 
                    estimate_costs
                    optimize_container_app
                    analyze_log_workspaces
                    check_search_tier
                    analyze_vms
                    ;;
                7) 
                    echo -e "${GREEN}👋 Goodbye!${NC}"
                    exit 0
                    ;;
                *) echo -e "${RED}Invalid option${NC}" ;;
            esac
            
            echo
            echo -n "Press Enter to continue..."
            read -r
            echo
        done
    else
        # Non-interactive mode - run all
        estimate_costs
        optimize_container_app
        analyze_log_workspaces
        check_search_tier
        analyze_vms
    fi
}

main "$@"
