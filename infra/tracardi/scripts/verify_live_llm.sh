#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-${ROOT_DIR}/.azure-config}"

RG="${AZURE_RESOURCE_GROUP:-rg-cdpmerged-fast}"
APP_NAME="${CONTAINER_APP_NAME:-ca-cdpmerged-fast}"
TAIL_LINES="${TAIL_LINES:-250}"

get_env_value() {
  local env_name="$1"
  az containerapp show \
    --name "${APP_NAME}" \
    --resource-group "${RG}" \
    --query "properties.template.containers[0].env[?name=='${env_name}'].value | [0]" \
    -o tsv
}

echo "Checking Container App runtime configuration..."
provider="$(get_env_value "LLM_PROVIDER" || true)"
tracardi_url="$(get_env_value "TRACARDI_API_URL" || true)"

if [[ -z "${provider}" ]]; then
  echo "Could not read LLM_PROVIDER from Container App env." >&2
  exit 1
fi

echo "LLM_PROVIDER=${provider}"
echo "TRACARDI_API_URL=${tracardi_url:-<unset>}"

if [[ "${provider}" == "mock" ]]; then
  echo "Validation failed: runtime provider is mock." >&2
  exit 1
fi

if [[ "${tracardi_url}" == "http://localhost:8686" ]]; then
  echo "Warning: Tracardi still points to localhost (expected before Phase B wiring)." >&2
fi

fqdn="$(
  az containerapp show \
    --name "${APP_NAME}" \
    --resource-group "${RG}" \
    --query "properties.configuration.ingress.fqdn" \
    -o tsv
)"

if [[ -z "${fqdn}" ]]; then
  echo "Could not resolve Container App FQDN." >&2
  exit 1
fi

echo "FQDN=${fqdn}"
echo "Checking Chainlit API settings endpoint..."
curl -fsS -H "Accept: application/json" "https://${fqdn}/project/settings" >/dev/null

echo "Scanning recent logs for real-model evidence..."
logs="$(
  az containerapp logs show \
    --name "${APP_NAME}" \
    --resource-group "${RG}" \
    --tail "${TAIL_LINES}" 2>&1 || true
)"

if grep -q "Mock response to:" <<<"${logs}"; then
  echo "Validation failed: found mock response marker in recent logs." >&2
  exit 1
fi

if grep -Eq "Retrying request to /chat/completions|RateLimitReached|openai\\.RateLimitError" <<<"${logs}"; then
  echo "Detected Azure OpenAI chat/completions activity in recent logs."
  echo "Validation passed: runtime is using real LLM calls (not mock)."
  exit 0
fi

echo "No explicit chat/completions marker found in the last ${TAIL_LINES} log lines." >&2
echo "Runtime config is still non-mock, but generate one UI/API chat turn and re-run this check for stronger evidence." >&2
