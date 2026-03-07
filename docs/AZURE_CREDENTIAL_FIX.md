# Azure Credential Authentication Error Fix

## Problem

When users ask a follow-up question (e.g., "Which ones have phone numbers?" after "How many restaurants in Antwerp?"), the app crashes with:

```
DefaultAzureCredential failed to retrieve a token from the included credentials.
Attempted credentials: EnvironmentCredential, WorkloadIdentityCredential, 
ManagedIdentityCredential, SharedTokenCacheCredential, VisualStudioCodeCredential,
AzureCliCredential, AzurePowerShellCredential, AzureDeveloperCliCredential, 
BrokerCredential
```

## Root Cause

1. **Default LLM Provider Mismatch**: The `.env.example` file set `LLM_PROVIDER=azure_openai` as default
2. **Azure Auth Default Behavior**: The code defaults to `AZURE_AUTH_USE_DEFAULT_CREDENTIAL=true`, which tries to use `DefaultAzureCredential`
3. **No Azure Credentials in Container**: The deployed container doesn't have Azure credentials (Managed Identity, Azure CLI, etc.)
4. **Error on LLM Invocation**: The error happens when the agent node tries to invoke the LLM on follow-up questions

## Files Changed

1. **`.env.example`**: Changed default `LLM_PROVIDER` from `azure_openai` to `openai`
2. **`infra/tracardi/scripts/update_containerapp.sh`**: 
   - Updated to use OpenAI as default
   - Added `AZURE_AUTH_USE_DEFAULT_CREDENTIAL=false` to prevent Azure credential errors
   - Added support for both OpenAI and Azure OpenAI providers
3. **`infra/tracardi/scripts/fix-azure-credential-error.sh`**: New script to fix the currently deployed container

## Immediate Fix for Deployed Container

### Option 1: Quick Fix with OpenAI (Recommended)

```bash
export OPENAI_API_KEY=sk-your-openai-key-here
cd /home/ff/.openclaw/workspace/CDP_Merged
bash infra/tracardi/scripts/fix-azure-credential-error.sh
```

### Option 2: Fix with Azure OpenAI

If you have Azure OpenAI configured:

```bash
export AZURE_OPENAI_API_KEY=your-azure-key
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
cd /home/ff/.openclaw/workspace/CDP_Merged
bash infra/tracardi/scripts/fix-azure-credential-error.sh
```

### Manual Fix

```bash
# Set OpenAI key as secret
az containerapp secret set \
    --name ca-cdpmerged-fast \
    --resource-group rg-cdpmerged-fast \
    --secrets openai-api-key=sk-your-key-here

# Update container to use OpenAI and disable Azure credential
az containerapp update \
    --name ca-cdpmerged-fast \
    --resource-group rg-cdpmerged-fast \
    --set-env-vars \
    LLM_PROVIDER=openai \
    OPENAI_API_KEY=secretref:openai-api-key \
    AZURE_AUTH_USE_DEFAULT_CREDENTIAL=false
```

## Verification

After applying the fix:

1. Wait 30-60 seconds for the container to restart
2. Open the app URL
3. Test initial query: "How many restaurants in Antwerp?"
4. Test follow-up: "Which ones have phone numbers?"
5. Both should work without Azure credential errors

## Configuration Reference

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `LLM_PROVIDER` | LLM backend to use | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | None |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | None |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | None |
| `AZURE_AUTH_USE_DEFAULT_CREDENTIAL` | Use Azure Default Credential | `false` |
| `AZURE_AUTH_ALLOW_KEY_FALLBACK` | Allow API key fallback | `true` |

## To Use Azure OpenAI in the Future

1. Set up Azure OpenAI service:
   ```bash
   bash infra/tracardi/scripts/azure_openai.sh print
   # Follow the printed commands to create and configure
   ```

2. Update the container:
   ```bash
   export LLM_PROVIDER=azure_openai
   export AZURE_OPENAI_API_KEY=your-key
   export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   bash infra/tracardi/scripts/update_containerapp.sh apply
   ```

## Troubleshooting

### Check Container Logs
```bash
az containerapp logs show \
    --name ca-cdpmerged-fast \
    --resource-group rg-cdpmerged-fast \
    --follow
```

### Verify Environment Variables
```bash
az containerapp show \
    --name ca-cdpmerged-fast \
    --resource-group rg-cdpmerged-fast \
    --query properties.configuration.secrets

az containerapp show \
    --name ca-cdpmerged-fast \
    --resource-group rg-cdpmerged-fast \
    --query properties.configuration.env
```

### Restart Container
```bash
az containerapp revision restart \
    --name ca-cdpmerged-fast \
    --resource-group rg-cdpmerged-fast
```
