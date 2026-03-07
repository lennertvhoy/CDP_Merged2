#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-${ROOT_DIR}/.azure-config}"

SUBSCRIPTION_PREFIX="${1:-ed}"

mkdir -p "${AZURE_CONFIG_DIR}"

az login --use-device-code

SUBSCRIPTION_ID="$(az account list --query "[?starts_with(id, '${SUBSCRIPTION_PREFIX}')].id | [0]" -o tsv)"
if [[ -z "${SUBSCRIPTION_ID}" ]]; then
  echo "No subscription found with prefix '${SUBSCRIPTION_PREFIX}'." >&2
  exit 1
fi

az account set --subscription "${SUBSCRIPTION_ID}"
az account show --query '{name:name,id:id,tenantId:tenantId}' -o table
