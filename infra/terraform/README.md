# Azure Terraform Deployment (~EUR 100/month)

This stack provisions a balanced CDP deployment on Azure:

- App VM (`Standard_B2s`): Tracardi API/GUI + MySQL + RabbitMQ + this agent container
- Elasticsearch VM (`Standard_B1ms`): dedicated single-node ES
- Azure Cache for Redis (Basic C0)
- Azure Event Hubs (Basic)
- Blob storage (LRS) for backups/snapshots
- Log Analytics + Application Insights
- Optional Azure AI Search service for RAG retrieval rollout

## Estimated Monthly Cost (West Europe)

- `Standard_B2s` VM: ~EUR 34-40
- `Standard_B1ms` VM: ~EUR 12-18
- Redis Basic C0: ~EUR 12-16
- Event Hubs Basic: ~EUR 10-12
- Storage + monitoring + egress baseline: ~EUR 8-15
- Total: ~EUR 90-101 (usage dependent)

## Prerequisites

1. Azure CLI logged in (`az login`)
2. Terraform >= 1.6
3. A pushed container image for this app (`agent_image`)
4. An RSA SSH public key for VM admin access

## Quick Start

```bash
# 1) login and select subscription prefix "ed"
scripts/azure/az_login.sh ed

# 2) prepare variables
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars

# 3) deploy
../../scripts/azure/tf.sh init
../../scripts/azure/tf.sh plan -var-file=terraform.tfvars
../../scripts/azure/tf.sh apply -var-file=terraform.tfvars

# 4) fetch endpoints
../../scripts/azure/tf.sh output
```

## Important Notes

- The app VM cloud-init deploys Docker Compose automatically.
- Tracardi uses managed Redis credentials (`REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`).
- Elasticsearch is private (`10.42.2.10` by default) and only reachable from app subnet.
- Restrict `admin_allowed_cidr` and `app_allowed_cidr` before production use.

## Azure AI Search + MI/KV Runtime Wiring (Phased Rollout)

- Provisioning is opt-in: set `enable_azure_search = true` to create `azurerm_search_service`.
- Backward-safe defaults keep Azure retrieval disabled:
  - `enable_azure_search_retrieval = false`
  - `enable_azure_search_shadow_mode = false`
  - `enable_citation_required = false`
- Runtime env wiring injects Azure Search settings via `agent_environment` merge in Terraform locals.
- Auth is MI/KV-first and rollout-safe:
  - `azure_auth_use_default_credential = true`
  - `azure_auth_allow_key_fallback = true`
  - `azure_auth_strict_mi_kv_only = false`
- Key Vault hooks:
  - `azure_key_vault_url` populates `AZURE_KEY_VAULT_URL`
  - `azure_key_vault_id` (optional) creates `Key Vault Secrets User` role assignment for app VM managed identity
  - `azure_search_api_key_secret_name` passes KV secret name for app-side resolution
- API-key handling:
  - preferred: MI token or KV secret name
  - fallback: `azure_search_api_key`
  - optional generated-key injection from provisioned search service: `azure_search_inject_admin_key = true` (default `false`)
