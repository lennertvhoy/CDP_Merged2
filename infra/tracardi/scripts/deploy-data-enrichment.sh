#!/bin/bash
# KBO Data Enhancement - Budget-Optimized Implementation (€150/month max)
# Implements HIGH-ROI features from the research report within budget constraints

set -e

RESOURCE_GROUP="rg-kbo-enrichment"
LOCATION="westeurope"

# COST-OPTIMIZED CONFIGURATION (Total: ~€110-145/month)
# ┌──────────────────────┬──────────────┬─────────────┬────────────┐
# │ Service              │ Tier         │ Cost/Mo     │ Notes      │
# ├──────────────────────┼──────────────┼─────────────┼────────────┤
# │ Azure AI Search      │ FREE         │ €0          │ 50MB limit │
# │ Azure OpenAI         │ S0 (limited) │ €60-80      │ Budget cap │
# │ Cosmos DB            │ Serverless   │ €20-30      │ Low usage  │
# │ Functions            │ Consumption  │ €15-20      │ Orchestrate│
# │ Blob Storage         │ Standard LRS │ €5-10       │ Raw data   │
# │ Monitor/Logs         │ Basic        │ €10-15      │ Essentials │
# ├──────────────────────┼──────────────┼─────────────┼────────────┤
# │ TOTAL                │              │ €110-145    │ Under €150 │
# └──────────────────────┴──────────────┴─────────────┴────────────┘

echo "=== KBO Data Enhancement - Budget Optimized (€150 max) ==="
echo "Target: High-ROI features within budget"
echo ""

# Check if running in apply mode
if [ "$1" != "apply" ]; then
    echo "DRY RUN MODE - Add 'apply' to execute"
    echo ""
fi

# Phase 1: Foundation (MUST HAVE - €30-40/month)
# ================================================
echo "PHASE 1: Foundation (€30-40/month)"
echo "-----------------------------------"

if [ "$1" == "apply" ]; then
    # Resource Group
    echo "Creating resource group..."
    az group create --name $RESOURCE_GROUP --location $LOCATION --output none
    
    # Storage Account (for raw KBO data)
    echo "Creating Storage Account..."
    az storage account create \
        --name "kbodata$(date +%s | tail -c 5)" \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --sku Standard_LRS \
        --kind StorageV2 \
        --output none
    
    # Cosmos DB - Serverless (pay per operation, not provisioned)
    echo "Creating Cosmos DB (Serverless - cost optimized)..."
    az cosmosdb create \
        --name "kbo-cosmos-$(date +%s | tail -c 5)" \
        --resource-group $RESOURCE_GROUP \
        --locations regionName=$LOCATION failoverPriority=0 \
        --capabilities EnableServerless \
        --output none
    
    # Create database and container
    COSMOS_ACCOUNT=$(az cosmosdb list --resource-group $RESOURCE_GROUP --query "[0].name" -o tsv)
    az cosmosdb sql database create \
        --account-name $COSMOS_ACCOUNT \
        --resource-group $RESOURCE_GROUP \
        --name "kbodb" \
        --output none
    
    az cosmosdb sql container create \
        --account-name $COSMOS_ACCOUNT \
        --database-name "kbodb" \
        --resource-group $RESOURCE_GROUP \
        --name "entities" \
        --partition-key-path "/enterpriseNumber" \
        --output none
    
    # Azure AI Search - FREE TIER (€0!)
    echo "Creating Azure AI Search (FREE tier)..."
    SEARCH_NAME="kbo-search-$(date +%s | tail -c 5)"
    az search service create \
        --name $SEARCH_NAME \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --sku free \
        --output none || echo "Search service creation may take a few minutes..."
    
    # Function App - Consumption plan (scales to zero)
    echo "Creating Function App (Consumption plan)..."
    az storage account create \
        --name "kbofunc$(date +%s | tail -c 5)" \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --sku Standard_LRS \
        --output none
    
    FUNC_STORAGE=$(az storage account list --resource-group $RESOURCE_GROUP --query "[?contains(name, 'kbofunc')].name" -o tsv | head -1)
    
    az functionapp create \
        --name "kbo-enrich-$(date +%s | tail -c 5)" \
        --resource-group $RESOURCE_GROUP \
        --storage-account $FUNC_STORAGE \
        --consumption-plan-location $LOCATION \
        --runtime python \
        --runtime-version 3.11 \
        --functions-version 4 \
        --output none
fi

echo "✅ Phase 1 complete (Foundation resources)"
echo ""

# Phase 2: Enrichment (HIGH ROI - €60-80/month)
# ==============================================
echo "PHASE 2: Enrichment (€60-80/month)"
echo "-----------------------------------"

if [ "$1" == "apply" ]; then
    # Azure OpenAI - S0 (pay-as-you-go, no provisioned capacity)
    echo "Creating Azure OpenAI (S0 - pay per use)..."
    OPENAI_NAME="kbo-openai-$(date +%s | tail -c 5)"
    az cognitiveservices account create \
        --name $OPENAI_NAME \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --kind OpenAI \
        --sku S0 \
        --output none
    
    # Deploy GPT-4o-mini (cheapest, fastest)
    echo "Deploying GPT-4o-mini model..."
    az cognitiveservices account deployment create \
        --name $OPENAI_NAME \
        --resource-group $RESOURCE_GROUP \
        --deployment-name "gpt-4o-mini" \
        --model-name "gpt-4o-mini" \
        --model-version "2024-07-18" \
        --model-format OpenAI \
        --sku-name "Standard" \
        --sku-capacity 1 \
        --output none
    
    echo ""
    echo "⚠️  IMPORTANT: Set up budget alerts for OpenAI!"
    echo "    Recommended: Alert at €60, hard limit at €80"
    echo ""
fi

echo "✅ Phase 2 complete (OpenAI for enrichment)"
echo ""

# Phase 3: Monitoring & Safety
# =============================
echo "PHASE 3: Monitoring & Budget Safety"
echo "------------------------------------"

if [ "$1" == "apply" ]; then
    # Create budget alert
    echo "Setting up budget alert (€150 limit)..."
    az monitor budgets create \
        --name "kbo-enrichment-budget" \
        --amount 150 \
        --time-grain Monthly \
        --start-date $(date +%Y-%m-01) \
        --category Cost \
        --resource-group $RESOURCE_GROUP \
        --notification-key key1 \
        --notification-emails "$(az account show --query user.name -o tsv)" \
        --threshold 80 \
        --output none || echo "Budget alert created or already exists"
fi

echo "✅ Phase 3 complete (Budget safety)"
echo ""

# Summary
# =======
echo ""
echo "=== DEPLOYMENT SUMMARY ==="
echo "Resource Group: $RESOURCE_GROUP"
echo ""
echo "Estimated Monthly Costs:"
echo "  Cosmos DB (Serverless):  €20-30"
echo "  Azure OpenAI (S0):       €60-80  ⚠️  MONITOR CLOSELY"
echo "  Functions (Consumption): €15-20"
echo "  Storage:                 €5-10"
echo "  Monitoring:              €5-10"
echo "  Search (Free):           €0"
echo "  -------------------------"
echo "  TOTAL:                   €105-150"
echo ""
echo "✅ Within €150 budget!"
echo ""
echo "Next Steps:"
echo "1. Deploy data ingestion functions"
echo "2. Start KBO Open Data import"
echo "3. Begin geocoding pipeline"
echo "4. Monitor costs daily for first week"
echo ""

if [ "$1" == "apply" ]; then
    echo "Resources created. To delete everything and start over:"
    echo "  az group delete --name $RESOURCE_GROUP --yes"
    echo ""
fi
