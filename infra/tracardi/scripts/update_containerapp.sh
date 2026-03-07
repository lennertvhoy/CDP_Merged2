#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-${ROOT_DIR}/.azure-config}"

MODE="${1:-print}"

RG="${AZURE_RESOURCE_GROUP:-rg-cdpmerged-fast}"
APP_NAME="${CONTAINER_APP_NAME:-ca-cdpmerged-fast}"

TRACARDI_API_URL="${TRACARDI_API_URL:-}"
TRACARDI_USERNAME="${TRACARDI_USERNAME:-admin@admin.com}"
TRACARDI_SOURCE_ID="${TRACARDI_SOURCE_ID:-kbo-source}"
TRACARDI_PASSWORD="${TRACARDI_PASSWORD:-}"
DATABASE_URL="${DATABASE_URL:-}"

# LLM Provider settings (default: openai)
LLM_PROVIDER="${LLM_PROVIDER:-openai}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"

# Azure OpenAI settings (only needed if LLM_PROVIDER=azure_openai)
AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-}"
AZURE_OPENAI_DEPLOYMENT_NAME="${AZURE_OPENAI_DEPLOYMENT_NAME:-${AZURE_OPENAI_DEPLOYMENT:-gpt-4o-mini}}"
AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:-}"

print_commands() {
  cat <<CMD
# Store secrets in Container App
az containerapp secret set \
  --name ${APP_NAME} \
  --resource-group ${RG} \
  --secrets openai-api-key='<OPENAI_API_KEY>' tracardi-password='<TRACARDI_PASSWORD>' database-url='<DATABASE_URL>'

# Update runtime environment variables
az containerapp update -n ${APP_NAME} -g ${RG} \
  --set-env-vars \
  LLM_PROVIDER=openai \
  OPENAI_API_KEY=secretref:openai-api-key \
  DATABASE_URL=secretref:database-url \
  AZURE_AUTH_USE_DEFAULT_CREDENTIAL=false \
  TRACARDI_API_URL='${TRACARDI_API_URL:-http://<tracardi-vm-ip>:8686}' \
  TRACARDI_USERNAME='${TRACARDI_USERNAME}' \
  TRACARDI_PASSWORD=secretref:tracardi-password \
  TRACARDI_SOURCE_ID='${TRACARDI_SOURCE_ID}'

# To use Azure OpenAI instead, set these environment variables:
#   LLM_PROVIDER=azure_openai \
#   AZURE_OPENAI_ENDPOINT='https://<resource>.openai.azure.com/' \
#   AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
#   AZURE_OPENAI_DEPLOYMENT_NAME='gpt-4o-mini' \
#   AZURE_OPENAI_DEPLOYMENT='gpt-4o-mini'
CMD
}

require_non_empty() {
  local name="$1"
  local value="$2"
  if [[ -z "${value}" ]]; then
    echo "Missing required value: ${name}" >&2
    exit 1
  fi
}

case "${MODE}" in
  print)
    print_commands
    ;;
  apply)
    require_non_empty "TRACARDI_API_URL" "${TRACARDI_API_URL}"
    require_non_empty "TRACARDI_PASSWORD" "${TRACARDI_PASSWORD}"
    require_non_empty "DATABASE_URL" "${DATABASE_URL}"

    if [[ "${LLM_PROVIDER}" == "azure_openai" ]]; then
      require_non_empty "AZURE_OPENAI_ENDPOINT" "${AZURE_OPENAI_ENDPOINT}"
      require_non_empty "AZURE_OPENAI_API_KEY" "${AZURE_OPENAI_API_KEY}"

      az containerapp secret set \
        --name "${APP_NAME}" \
        --resource-group "${RG}" \
        --secrets "azure-openai-key=${AZURE_OPENAI_API_KEY}" "tracardi-password=${TRACARDI_PASSWORD}" "database-url=${DATABASE_URL}"

      az containerapp update -n "${APP_NAME}" -g "${RG}" \
        --set-env-vars \
        LLM_PROVIDER=azure_openai \
        "AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}" \
        AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
        "AZURE_OPENAI_DEPLOYMENT_NAME=${AZURE_OPENAI_DEPLOYMENT_NAME}" \
        "AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT_NAME}" \
        DATABASE_URL=secretref:database-url \
        "TRACARDI_API_URL=${TRACARDI_API_URL}" \
        "TRACARDI_USERNAME=${TRACARDI_USERNAME}" \
        TRACARDI_PASSWORD=secretref:tracardi-password \
        "TRACARDI_SOURCE_ID=${TRACARDI_SOURCE_ID}"
    else
      # Default: OpenAI
      require_non_empty "OPENAI_API_KEY" "${OPENAI_API_KEY}"

      az containerapp secret set \
        --name "${APP_NAME}" \
        --resource-group "${RG}" \
        --secrets "openai-api-key=${OPENAI_API_KEY}" "tracardi-password=${TRACARDI_PASSWORD}" "database-url=${DATABASE_URL}"

      az containerapp update -n "${APP_NAME}" -g "${RG}" \
        --set-env-vars \
        LLM_PROVIDER=openai \
        OPENAI_API_KEY=secretref:openai-api-key \
        DATABASE_URL=secretref:database-url \
        AZURE_AUTH_USE_DEFAULT_CREDENTIAL=false \
        "TRACARDI_API_URL=${TRACARDI_API_URL}" \
        "TRACARDI_USERNAME=${TRACARDI_USERNAME}" \
        TRACARDI_PASSWORD=secretref:tracardi-password \
        "TRACARDI_SOURCE_ID=${TRACARDI_SOURCE_ID}"
    fi
    ;;
  *)
    cat <<USAGE
Usage: infra/tracardi/scripts/update_containerapp.sh <print|apply>

Environment variables required for apply mode:
  TRACARDI_API_URL=http://<tracardi-vm-ip>:8686
  TRACARDI_PASSWORD=<strong-password>
  DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>?sslmode=require

LLM Provider settings (default: openai):
  LLM_PROVIDER=openai                    # Options: openai, azure_openai
  OPENAI_API_KEY=<openai-api-key>        # Required if LLM_PROVIDER=openai

For Azure OpenAI (set LLM_PROVIDER=azure_openai):
  AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
  AZURE_OPENAI_API_KEY=<azure-api-key>
  AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
  AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini    # legacy fallback

Optional:
  CONTAINER_APP_NAME=ca-cdpmerged-fast
  AZURE_RESOURCE_GROUP=rg-cdpmerged-fast
  TRACARDI_USERNAME=admin@admin.com
  TRACARDI_SOURCE_ID=kbo-source
USAGE
    exit 1
    ;;
esac
