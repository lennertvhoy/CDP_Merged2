#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform"
export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-${ROOT_DIR}/.azure-config}"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is not installed. Install Terraform >= 1.6 and retry." >&2
  exit 1
fi

ACTION="${1:-}"
shift || true

case "${ACTION}" in
  init)
    terraform -chdir="${TF_DIR}" init "$@"
    ;;
  plan)
    terraform -chdir="${TF_DIR}" plan "$@"
    ;;
  apply)
    terraform -chdir="${TF_DIR}" apply "$@"
    ;;
  destroy)
    terraform -chdir="${TF_DIR}" destroy "$@"
    ;;
  output)
    terraform -chdir="${TF_DIR}" output "$@"
    ;;
  *)
    cat <<USAGE
Usage: scripts/azure/tf.sh <init|plan|apply|destroy|output> [terraform args]

Examples:
  scripts/azure/tf.sh init
  scripts/azure/tf.sh plan -var-file=terraform.tfvars
  scripts/azure/tf.sh apply -var-file=terraform.tfvars
  scripts/azure/tf.sh output chainlit_url
USAGE
    exit 1
    ;;
esac
