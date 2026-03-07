#!/bin/bash
# Dev Mode Deployment Script for CDP_Merged
# Cost-optimized for development (~€100-130/month budget)
# Usage: bash infra/tracardi/scripts/deploy-dev.sh apply

set -e

RESOURCE_GROUP="rg-cdpmerged-dev"
LOCATION="westeurope"
APP_NAME="ca-cdpmerged-dev"
SEARCH_SERVICE="cdpmerged-search-dev"
OPENAI_SERVICE="aoai-cdpmerged-dev"
ACR_NAME="cdpmergeddevacr"

# Cost-optimized Container App spec (dev mode)
CONTAINER_CPU="0.25"        # Reduced from 0.5
CONTAINER_MEMORY="0.5Gi"    # Reduced from 1Gi
MIN_REPLICAS="0"            # Scale to zero (huge savings)
MAX_REPLICAS="3"            # Lower max for dev

# Free/low-cost tiers for dev
SEARCH_SKU="free"           # Free tier (50MB limit)
OPENAI_SKU="S0"             # Pay-as-you-go (no provisioned throughput)

echo "=== CDP_Merged Dev Deployment ==="
echo "Estimated monthly cost: €100-130"
echo "Resource Group: $RESOURCE_GROUP"
echo ""

if [ "$1" != "apply" ]; then
    echo "DRY RUN MODE (add 'apply' to execute)"
    echo ""
fi

# Create resource group (if not exists)
if [ "$1" == "apply" ]; then
    echo "Creating resource group..."
    az group create --name $RESOURCE_GROUP --location $LOCATION --output none
fi

# Container Registry (Basic SKU for dev)
if [ "$1" == "apply" ]; then
    echo "Creating Container Registry (Basic SKU)..."
    az acr create \
        --resource-group $RESOURCE_GROUP \
        --name $ACR_NAME \
        --sku Basic \
        --location $LOCATION \
        --admin-enabled true \
        --output none
fi

# Azure AI Search (FREE tier for dev)
if [ "$1" == "apply" ]; then
    echo "Creating Azure AI Search (FREE tier - 50MB limit)..."
    az search service create \
        --name $SEARCH_SERVICE \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --sku free \
        --output none || echo "Search service already exists"
fi

# Azure OpenAI (Pay-as-you-go, no provisioned)
if [ "$1" == "apply" ]; then
    echo "Creating Azure OpenAI (S0 - pay-as-you-go)..."
    az cognitiveservices account create \
        --name $OPENAI_SERVICE \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --kind OpenAI \
        --sku S0 \
        --output none || echo "OpenAI service already exists"
    
    # Deploy gpt-4o-mini model
    echo "Deploying gpt-4o-mini model..."
    az cognitiveservices account deployment create \
        --name $OPENAI_SERVICE \
        --resource-group $RESOURCE_GROUP \
        --deployment-name gpt-4o-mini \
        --model-name gpt-4o-mini \
        --model-version "2024-07-18" \
        --model-format OpenAI \
        --sku-capacity 1 \
        --sku-name Standard \
        --output none || echo "Model deployment already exists"
fi

# Log Analytics (Per GB tier for dev)
if [ "$1" == "apply" ]; then
    echo "Creating Log Analytics workspace..."
    az monitor log-analytics workspace create \
        --resource-group $RESOURCE_GROUP \
        --name "law-cdpmerged-dev" \
        --location $LOCATION \
        --sku PerGB2018 \
        --output none || echo "Workspace already exists"
fi

# Container App Environment (Consumption only)
if [ "$1" == "apply" ]; then
    echo "Creating Container App Environment..."
    az containerapp env create \
        --resource-group $RESOURCE_GROUP \
        --name "cae-cdpmerged-dev" \
        --location $LOCATION \
        --logs-workspace-id $(az monitor log-analytics workspace show --resource-group $RESOURCE_GROUP --name "law-cdpmerged-dev" --query customerId -o tsv) \
        --logs-workspace-key $(az monitor log-analytics workspace get-shared-keys --resource-group $RESOURCE_GROUP --name "law-cdpmerged-dev" --query primarySharedKey -o tsv) \
        --output none || echo "Environment already exists"
fi

# Get API keys for configuration
if [ "$1" == "apply" ]; then
    echo "Retrieving API keys..."
    SEARCH_KEY=$(az search admin-key show --resource-group $RESOURCE_GROUP --service-name $SEARCH_SERVICE --query primaryKey -o tsv)
    OPENAI_KEY=$(az cognitiveservices account keys list --name $OPENAI_SERVICE --resource-group $RESOURCE_GROUP --query key1 -o tsv)
    OPENAI_ENDPOINT=$(az cognitiveservices account show --name $OPENAI_SERVICE --resource-group $RESOURCE_GROUP --query properties.endpoint -o tsv)
fi

# Container App (Cost-optimized)
if [ "$1" == "apply" ]; then
    echo "Creating Container App (cost-optimized spec)..."
    az containerapp create \
        --resource-group $RESOURCE_GROUP \
        --name $APP_NAME \
        --environment "cae-cdpmerged-dev" \
        --image "ghcr.io/lennertvhoy/cdp_merged:latest" \
        --target-port 8000 \
        --ingress external \
        --cpu $CONTAINER_CPU \
        --memory $CONTAINER_MEMORY \
        --min-replicas $MIN_REPLICAS \
        --max-replicas $MAX_REPLICAS \
        --env-vars \
            LLM_PROVIDER=azure_openai \
            AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT \
            AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini \
            AZURE_AUTH_USE_DEFAULT_CREDENTIAL=false \
            AZURE_SEARCH_ENDPOINT=https://$SEARCH_SERVICE.search.windows.net \
            AZURE_SEARCH_INDEX_NAME=companies \
            RESEND_FROM_EMAIL=onboarding@resend.dev \
            TRACARDI_API_URL=http://52.148.232.140:8686 \
            TRACARDI_SOURCE_ID=kbo-source \
            TRACARDI_USERNAME=admin \
            FLEXMAIL_ENABLED=false \
        --secrets \
            azure-openai-key=$OPENAI_KEY \
            azure-search-api-key=$SEARCH_KEY \
            resend-api-key=placeholder \
            tracardi-password=<redacted> \
        --output none || echo "Container app already exists, updating..."
fi

# Set secret references
if [ "$1" == "apply" ]; then
    echo "Configuring secret references..."
    az containerapp update \
        --resource-group $RESOURCE_GROUP \
        --name $APP_NAME \
        --set-env-vars \
            AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
            AZURE_SEARCH_API_KEY=secretref:azure-search-api-key \
            RESEND_API_KEY=secretref:resend-api-key \
            TRACARDI_PASSWORD=secretref:tracardi-password \
        --output none
fi

echo ""
echo "=== Deployment Complete ==="
echo "Container App URL:"
az containerapp show --resource-group $RESOURCE_GROUP --name $APP_NAME --query properties.configuration.ingress.fqdn -o tsv
echo ""
echo "=== Cost Summary ==="
echo "Container App: ~€5-15/month (scale-to-zero)"
echo "Azure OpenAI: ~€20-50/month (pay-as-you-go)"
echo "Azure Search: FREE (50MB limit)"
echo "Container Registry: ~€5/month (Basic)"
echo "Log Analytics: ~€5-10/month (light usage)"
echo "----------------------------"
echo "TOTAL: ~€35-80/month (well under €150 budget)"
echo ""
echo "Note: Tracardi runs separately - not included in this estimate"
