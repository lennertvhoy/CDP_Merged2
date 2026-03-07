#!/usr/bin/env bash
# Quick fix for Azure credential authentication error in deployed CDP_Merged app
# This script fixes the "DefaultAzureCredential failed to retrieve a token" error

set -euo pipefail

RG="${AZURE_RESOURCE_GROUP:-rg-cdpmerged-fast}"
APP_NAME="${CONTAINER_APP_NAME:-ca-cdpmerged-fast}"

echo "=== Azure Credential Error Fix for CDP_Merged ==="
echo ""
echo "This fix disables Azure Default Credential and switches to OpenAI provider."
echo ""

# Check if user wants to proceed
echo "Target: Container App '${APP_NAME}' in Resource Group '${RG}'"
echo ""

# Option 1: Quick fix with OpenAI (recommended)
echo "Option 1: Quick fix (OpenAI) - Requires OPENAI_API_KEY"
echo "Option 2: Fix with Azure OpenAI - Requires AZURE_OPENAI_API_KEY and endpoint"
echo ""

if [[ -z "${OPENAI_API_KEY:-}" && -z "${AZURE_OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: Please set either OPENAI_API_KEY or AZURE_OPENAI_API_KEY environment variable."
    echo ""
    echo "Examples:"
    echo "  export OPENAI_API_KEY=sk-your-key-here"
    echo "  # OR"
    echo "  export AZURE_OPENAI_API_KEY=your-azure-key"
    echo "  export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/"
    exit 1
fi

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    echo "Using OpenAI provider..."
    
    # Store the OpenAI key as a secret
    az containerapp secret set \
        --name "${APP_NAME}" \
        --resource-group "${RG}" \
        --secrets "openai-api-key=${OPENAI_API_KEY}"
    
    # Update environment variables to use OpenAI and disable Azure credential
    az containerapp update \
        --name "${APP_NAME}" \
        --resource-group "${RG}" \
        --set-env-vars \
        LLM_PROVIDER=openai \
        OPENAI_API_KEY=secretref:openai-api-key \
        AZURE_AUTH_USE_DEFAULT_CREDENTIAL=false
    
    echo ""
    echo "✅ Fix applied successfully!"
    echo ""
    echo "The app is now configured to:"
    echo "  - Use OpenAI provider (not Azure OpenAI)"
    echo "  - Disable Azure Default Credential (prevents the error)"
    echo ""
    
elif [[ -n "${AZURE_OPENAI_API_KEY:-}" ]]; then
    echo "Using Azure OpenAI provider..."
    
    if [[ -z "${AZURE_OPENAI_ENDPOINT:-}" ]]; then
        echo "ERROR: AZURE_OPENAI_ENDPOINT is required when using Azure OpenAI."
        echo "Example: export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/"
        exit 1
    fi
    
    # Store the Azure OpenAI key as a secret
    az containerapp secret set \
        --name "${APP_NAME}" \
        --resource-group "${RG}" \
        --secrets "azure-openai-key=${AZURE_OPENAI_API_KEY}"
    
    # Update environment variables to use Azure OpenAI with explicit key
    az containerapp update \
        --name "${APP_NAME}" \
        --resource-group "${RG}" \
        --set-env-vars \
        LLM_PROVIDER=azure_openai \
        AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT}" \
        AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
        AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini \
        AZURE_AUTH_USE_DEFAULT_CREDENTIAL=false \
        AZURE_AUTH_ALLOW_KEY_FALLBACK=true
    
    echo ""
    echo "✅ Fix applied successfully!"
    echo ""
    echo "The app is now configured to:"
    echo "  - Use Azure OpenAI provider with explicit API key"
    echo "  - Disable Azure Default Credential (prevents the error)"
    echo "  - Allow key fallback for authentication"
    echo ""
fi

echo "Verify the fix:"
echo "  1. Wait 30-60 seconds for the container to restart"
echo "  2. Open the app URL in browser"
echo "  3. Ask: 'How many restaurants in Antwerp?'"
echo "  4. Follow up: 'Which ones have phone numbers?'"
echo ""
echo "To check logs:"
echo "  az containerapp logs show --name ${APP_NAME} --resource-group ${RG} --follow"
