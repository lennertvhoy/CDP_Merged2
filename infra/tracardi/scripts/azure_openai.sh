#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-${ROOT_DIR}/.azure-config}"

ACTION="${1:-help}"

RG="${AZURE_RESOURCE_GROUP:-rg-cdpmerged-fast}"
LOCATION="${AZURE_LOCATION:-westeurope}"
AOAI_NAME="${AZURE_OPENAI_NAME:-aoai-cdpmerged-fast}"
DEPLOYMENT_NAME="${AZURE_OPENAI_DEPLOYMENT_NAME:-${AZURE_OPENAI_DEPLOYMENT:-gpt-4o-mini}}"
MODEL_NAME="${AZURE_OPENAI_MODEL:-gpt-4o-mini}"
MODEL_VERSION="${AZURE_OPENAI_MODEL_VERSION:-2024-07-18}"
CAPACITY="${AZURE_OPENAI_CAPACITY:-10}"
SKU_NAME="${AZURE_OPENAI_SKU_NAME:-GlobalStandard}"

print_commands() {
  cat <<CMD
# 1) Create Azure OpenAI account (billable)
az cognitiveservices account create \
  --name ${AOAI_NAME} \
  --resource-group ${RG} \
  --location ${LOCATION} \
  --kind OpenAI \
  --sku S0 \
  --custom-domain ${AOAI_NAME}

# 2) Deploy GPT-4o-mini model (billable)
az cognitiveservices account deployment create \
  --resource-group ${RG} \
  --name ${AOAI_NAME} \
  --deployment-name ${DEPLOYMENT_NAME} \
  --model-format OpenAI \
  --model-name ${MODEL_NAME} \
  --model-version ${MODEL_VERSION} \
  --sku-name ${SKU_NAME} \
  --sku-capacity ${CAPACITY}

# 3) Retrieve endpoint + key
az cognitiveservices account show --name ${AOAI_NAME} --resource-group ${RG} --query properties.endpoint -o tsv
az cognitiveservices account keys list --name ${AOAI_NAME} --resource-group ${RG} --query key1 -o tsv
CMD
}

case "${ACTION}" in
  print)
    print_commands
    ;;
  create)
    az cognitiveservices account create \
      --name "${AOAI_NAME}" \
      --resource-group "${RG}" \
      --location "${LOCATION}" \
      --kind OpenAI \
      --sku S0 \
      --custom-domain "${AOAI_NAME}"
    ;;
  deploy)
    az cognitiveservices account deployment create \
      --resource-group "${RG}" \
      --name "${AOAI_NAME}" \
      --deployment-name "${DEPLOYMENT_NAME}" \
      --model-format OpenAI \
      --model-name "${MODEL_NAME}" \
      --model-version "${MODEL_VERSION}" \
      --sku-name "${SKU_NAME}" \
      --sku-capacity "${CAPACITY}"
    ;;
  show)
    ENDPOINT="$(az cognitiveservices account show --name "${AOAI_NAME}" --resource-group "${RG}" --query properties.endpoint -o tsv)"
    KEY="$(az cognitiveservices account keys list --name "${AOAI_NAME}" --resource-group "${RG}" --query key1 -o tsv)"
    cat <<OUT
AZURE_OPENAI_ENDPOINT=${ENDPOINT}
AZURE_OPENAI_DEPLOYMENT_NAME=${DEPLOYMENT_NAME}
AZURE_OPENAI_DEPLOYMENT=${DEPLOYMENT_NAME}
AZURE_OPENAI_API_KEY=${KEY}
OUT
    ;;
  *)
    cat <<USAGE
Usage: infra/tracardi/scripts/azure_openai.sh <print|create|deploy|show>

Recommended sequence:
  infra/tracardi/scripts/azure_openai.sh print
  infra/tracardi/scripts/azure_openai.sh create
  infra/tracardi/scripts/azure_openai.sh deploy
  infra/tracardi/scripts/azure_openai.sh show
USAGE
    exit 1
    ;;
esac
