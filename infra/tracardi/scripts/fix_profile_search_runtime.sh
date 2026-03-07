#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT_DIR="${ROOT_DIR}/infra/tracardi/scripts"

AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-/tmp/azure-config}"
TRACARDI_RESOURCE_GROUP="${TRACARDI_RESOURCE_GROUP:-rg-cdpmerged-fast}"
TRACARDI_APP_VM="${TRACARDI_APP_VM:-vm-tracardi-cdpmerged-prod}"
TRACARDI_DATA_VM="${TRACARDI_DATA_VM:-vm-data-cdpmerged-prod}"

run_remote() {
  local vm_name="$1"
  local script_name="$2"

  env AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR}" az vm run-command invoke \
    -g "${TRACARDI_RESOURCE_GROUP}" \
    -n "${vm_name}" \
    --command-id RunShellScript \
    --scripts @"${SCRIPT_DIR}/${script_name}"
}

echo "Applying wildcard search hotfix on ${TRACARDI_APP_VM}..."
run_remote "${TRACARDI_APP_VM}" "hotfix_profile_search_vm.sh"

echo
echo "Backfilling metadata.time.update on ${TRACARDI_DATA_VM}..."
run_remote "${TRACARDI_DATA_VM}" "backfill_profile_update_time_vm.sh"
