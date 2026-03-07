# Deployment Guide — CDP_Merged

## Tracardi + Azure OpenAI (Host Deployment Spec, Option B Recommended)

This section is the host-side deployment runbook for:

- Existing app: `ca-cdpmerged-fast` in `rg-cdpmerged-fast`
- New stack: Tracardi API/GUI + Elasticsearch + Redis
- LLM provider: Azure OpenAI (`gpt-4o-mini`)

### 1. Pre-Apply Guardrails (Required)

```bash
export AZURE_CONFIG_DIR=/home/ff/Documents/CDP_Merged/.azure-config
az account set --subscription ed9400bc-d5eb-4aa6-8b3f-2d4c11b17b9f
```

- Run a Terraform dry-run first (`plan`).
- Confirm cost estimate before any `apply`.
- Get explicit go-ahead before creating billable resources.

### 2. Tracardi Infrastructure (Terraform)

New stack location:

- `infra/tracardi`

Architecture implemented (Option B):

- `Standard_B2s` VM: Tracardi API (`8686`) + GUI (`8787`)
- `Standard_B1ms` VM: Elasticsearch (`9200`) + Redis (`6379`)
- Blob container for Elasticsearch snapshots

Security controls in this stack:

- SSH (`22`) only from `admin_allowed_cidr`
- Tracardi GUI (`8787`) only from `office_allowed_cidr`
- Tracardi API (`8686`) from office CIDR and Container App subnet CIDR
- Elasticsearch/Redis only from Tracardi subnet and Container App subnet CIDR
- SSH key authentication only (`disable_password_authentication = true`)

Bootstrap behavior via cloud-init:

1. Install Docker + Docker Compose plugin.
2. Write `/opt/tracardi/docker-compose.yml`.
3. Run `docker compose up -d`.
4. Install `/opt/tracardi/healthcheck.sh`.

Dry-run commands:

```bash
cd /home/ff/Documents/CDP_Merged/infra/tracardi
cp terraform.tfvars.example terraform.tfvars
# Fill: admin_ssh_public_key, admin_allowed_cidr, office_allowed_cidr, container_app_subnet_cidr

./scripts/tf.sh init
./scripts/tf.sh plan -var-file=terraform.tfvars
```

Helper commands to discover `container_app_subnet_cidr`:

```bash
ENV_ID="$(az containerapp show -n ca-cdpmerged-fast -g rg-cdpmerged-fast --query properties.environmentId -o tsv)"
INFRA_SUBNET_ID="$(az containerapp env show --ids "${ENV_ID}" --query properties.vnetConfiguration.infrastructureSubnetId -o tsv)"
az network vnet subnet show --ids "${INFRA_SUBNET_ID}" --query addressPrefix -o tsv
```

If `infrastructureSubnetId` is `null`, the Container App environment is not VNet-injected yet. In that case, complete this first:

1. Create a VNet-integrated Container Apps Environment with a dedicated subnet.
2. Move/redeploy `ca-cdpmerged-fast` into that environment.
3. Use that subnet CIDR as `container_app_subnet_cidr`.

Temporary exception for timeline-critical testing (track and expire):

- Do not expose Elasticsearch (`9200`) or Redis (`6379`) publicly.
- Keep Tracardi API (`8686`) reachable only from `office_allowed_cidr` until the app is moved to a VNet-injected Container Apps Environment.
- Record an expiry date for this exception and remove it immediately after VNet migration.
- Removal condition: rerun `infra/tracardi` with the real Container App subnet CIDR, then drop any temporary office-only fallback rules that were added only for this gap.

Apply commands (only after explicit approval):

```bash
./scripts/tf.sh apply -var-file=terraform.tfvars
./scripts/tf.sh output
```

Expected Terraform outputs include:

- Tracardi VM public IP
- `tracardi_api_url`, `tracardi_gui_url`
- ES/Redis connection strings
- snapshot storage connection string and container URL

### 3. Azure OpenAI Setup (`westeurope`, GPT-4o-mini)

Script location:

- `infra/tracardi/scripts/azure_openai.sh`

Preview commands first:

```bash
cd /home/ff/Documents/CDP_Merged/infra/tracardi
./scripts/azure_openai.sh print
```

Create + deploy (billable; run only after approval):

```bash
./scripts/azure_openai.sh create
./scripts/azure_openai.sh deploy
./scripts/azure_openai.sh show
```

`show` returns:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT_NAME` (default: `gpt-4o-mini`)
- `AZURE_OPENAI_DEPLOYMENT` (legacy compatibility alias)
- `AZURE_OPENAI_API_KEY`

### 4. Integrate with Existing Container App

Script location:

- `infra/tracardi/scripts/update_containerapp.sh`

Preview:

```bash
cd /home/ff/Documents/CDP_Merged/infra/tracardi
./scripts/update_containerapp.sh print
```

Apply (after setting real values):

```bash
export TRACARDI_API_URL=http://<tracardi-vm-ip>:8686
export TRACARDI_PASSWORD='<strong-password>'
export AZURE_OPENAI_ENDPOINT='https://<resource>.openai.azure.com/'
export AZURE_OPENAI_API_KEY='<api-key>'
export AZURE_OPENAI_DEPLOYMENT_NAME='gpt-4o-mini'
export TRACARDI_USERNAME='admin'
export TRACARDI_SOURCE_ID='kbo-source'

./scripts/update_containerapp.sh apply
```

Equivalent update command used by the script:

```bash
az containerapp update -n ca-cdpmerged-fast -g rg-cdpmerged-fast \
  --set-env-vars \
  LLM_PROVIDER=azure_openai \
  AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/ \
  AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
  AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini \
  AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini \
  TRACARDI_API_URL=http://<tracardi-vm-ip>:8686 \
  TRACARDI_USERNAME=admin \
  TRACARDI_PASSWORD=secretref:tracardi-password \
  TRACARDI_SOURCE_ID=kbo-source
```

### 5. Cost Breakdown (Target Envelope)

| Component | Cost |
|---|---|
| CDP_Merged Container App | EUR 10-15 |
| Tracardi VM (`B2s`) | EUR 35 |
| Data VM (`B1ms`) | EUR 13 |
| Azure OpenAI | EUR 5-10 |
| Storage/Network | EUR 5-10 |
| Total | EUR 68-83 |

### 6. Verification Commands

```bash
# Tracardi API health
curl http://<tracardi-ip>:8686/health

# Tracardi GUI
curl http://<tracardi-ip>:8787

# Elasticsearch (private; run from Tracardi VM or another trusted source)
ssh azureuser@<tracardi-ip> "curl -fsS http://<data-private-ip>:9200/_cluster/health"

# Redis (private; run from Tracardi VM or another trusted source)
ssh azureuser@<tracardi-ip> "redis-cli -h <data-private-ip> -a '<redis-password>' ping"

# CDP_Merged integration test
curl https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/project/settings
```

### 7. CI/CD Deployment Pipeline

Workflows:

- `.github/workflows/ci.yml`: lint, type-check, unit tests, bandit + dependency vulnerability audit
- `.github/workflows/cd.yml`: migration release gates (citation/shadow tests), image build/push, Trivy scan, staged promotion (`staging` -> `production`) with environment approvals
- `.github/workflows/infra-tracardi.yml`: Terraform `fmt`, `validate`, `tfsec`, `plan`
- `.github/workflows/infra-terraform.yml`: Terraform `fmt`, `validate`, `tfsec`, `plan` for `infra/terraform` with Azure Search + rollout variable awareness

CD behavior:

- Push to `main`: run migration release gates, build image, run image scan, deploy `staging`, run smoke checks, then promote to `production` (gated by production environment approvals)
- `workflow_dispatch`: manual deploy to `staging` or `production`
- Production gate: enforced by GitHub Environment protection on `production`

CI behavior updates:

- Secret detection runs via gitleaks on every push/PR (`.github/workflows/ci.yml`)
- Migration flag gates run focused test suites for:
  - `ENABLE_CITATION_REQUIRED`
  - `ENABLE_AZURE_SEARCH_SHADOW_MODE`
  - `ENABLE_AZURE_SEARCH_RETRIEVAL`
- Gate logs + JUnit output are uploaded as artifacts for release/audit visibility
- Optional integration gate toggle: set repository/environment variable `RUN_INTEGRATION_GATES=true`

Required GitHub Environment configuration:

1. Environment `staging`
   - Variable: `AZURE_CLIENT_ID`
   - Variable: `AZURE_TENANT_ID`
   - Variable: `AZURE_SUBSCRIPTION_ID`
   - Variable: `AZURE_RESOURCE_GROUP`
   - Variable: `AZURE_CONTAINERAPP_NAME`
   - Optional Variable: `RUN_INTEGRATION_GATES` (`true` to enforce migration integration gates)
2. Environment `production`
   - Variable: `AZURE_CLIENT_ID`
   - Variable: `AZURE_TENANT_ID`
   - Variable: `AZURE_SUBSCRIPTION_ID`
   - Variable: `AZURE_RESOURCE_GROUP`
   - Variable: `AZURE_CONTAINERAPP_NAME`
   - Optional Variable: `RUN_INTEGRATION_GATES` (`true` to enforce migration integration gates)
   - Required reviewers enabled (manual gate)

Infra plan workflows (`infra-tracardi.yml`, `infra-terraform.yml`) require the same Azure OIDC variables on the selected environment (currently `staging`) for `azure/login@v2`.

### 8. Rollback Procedure (Container Apps)

Rollback to previous revision (fastest):

```bash
az containerapp revision list \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "[].{name:name,active:properties.active,created:properties.createdTime}" -o table

az containerapp ingress traffic set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --revision-weight <previous-revision-name>=100
```

Rollback to previous image (new revision from known good tag):

```bash
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --image ghcr.io/lennertvhoy/CDP_Merged:<known-good-tag>
```

Post-rollback validation:

```bash
curl -fsS -H "Accept: application/json" \
  https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/project/settings
```

## Docker Compose (Recommended)

The included `docker-compose.yml` starts all infrastructure services.

### 1. Prerequisites

- Docker Engine ≥ 24.0
- Docker Compose ≥ 2.20
- At least 4 GB RAM allocated to Docker

### 2. Start Infrastructure

```bash
# Start all services (detached)
make docker-up

# Services started:
# - Elasticsearch: http://localhost:9200
# - Tracardi API:  http://localhost:8686
# - Tracardi GUI:  http://localhost:8787
# - Redis:         localhost:6379
# - MySQL:         localhost:3306
# - Wiremock:      http://localhost:8080 (Flexmail mock)
```

### 3. Configure Environment

```bash
# Copy example env
cp .env.example .env

# Required changes:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...    ← your key
# Or set LLM_PROVIDER=ollama and install Ollama locally
```

### 4. Run the Application

```bash
# Development mode (hot-reload)
make dev

# Or directly:
poetry run chainlit run src/app.py --watch
```

The chat interface will be available at **http://localhost:8000**.

### 5. Load KBO Data

```bash
# Run the KBO data seeding script
./scripts/seed_data.sh

# Or manually:
poetry run python -c "
from src.ingestion.tracardi_loader import load_kbo_data
import asyncio
asyncio.run(load_kbo_data('path/to/kbo.csv'))
"
```

---

## Azure Terraform Deployment (~EUR 100/month target)

This repository now includes Terraform for a balanced Azure deployment:

- `Standard_B2s` app VM (Tracardi API/GUI + MySQL + RabbitMQ + agent app)
- `Standard_B1ms` Elasticsearch VM (isolated private endpoint)
- Azure Cache for Redis (Basic C0)
- Azure Event Hubs (Basic)
- Blob storage + Application Insights/Log Analytics

### 1. Authenticate Azure CLI (subscription prefix `ed`)

```bash
make az-login SUB_PREFIX=ed
```

The helper script sets `AZURE_CONFIG_DIR` to a repo-local directory and selects the first subscription id that starts with `ed`.

### 2. Prepare Terraform variables

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars (SSH key, agent image, OPENAI_API_KEY, FLEXMAIL_* ...)
```

Use an `ssh-rsa ...` public key for `admin_ssh_public_key` (Azure rejected `ssh-ed25519` during validation).

### 3. Deploy infrastructure

```bash
make tf-init
make tf-plan TFVARS=infra/terraform/terraform.tfvars
make tf-apply TFVARS=infra/terraform/terraform.tfvars
```

### 4. Read endpoints and generated secrets

```bash
make tf-output
```

Key outputs:
- `chainlit_url`
- `tracardi_api_url`
- `tracardi_gui_url`
- `mysql_password` (sensitive)
- `tracardi_admin_password` (sensitive)

### 5. Destroy when finished

```bash
make tf-destroy TFVARS=infra/terraform/terraform.tfvars
```

See `infra/terraform/README.md` for detailed notes and cost envelope.

---

## Azure Container Apps (Fastest path)

This is the quickest path to get a public URL with minimal infra.

### 1. Build image locally

```bash
docker build -t cdp-merged:local .
```

### 2. Create/prepare Azure resources

```bash
AZURE_CONFIG_DIR=$(pwd)/.azure-config az group create -n rg-cdpmerged-fast -l westeurope
AZURE_CONFIG_DIR=$(pwd)/.azure-config az containerapp env create -n ca-cdpmerged-fast-env -g rg-cdpmerged-fast -l westeurope
AZURE_CONFIG_DIR=$(pwd)/.azure-config az acr create -n <acr_name> -g rg-cdpmerged-fast --sku Basic --admin-enabled true
```

### 3. Push image to ACR

```bash
AZURE_CONFIG_DIR=$(pwd)/.azure-config az acr credential show -n <acr_name>
docker login <acr_name>.azurecr.io -u <acr_name> -p <acr_password>
docker tag cdp-merged:local <acr_name>.azurecr.io/cdp-merged:mock-<tag>
docker push <acr_name>.azurecr.io/cdp-merged:mock-<tag>
```

### 4. Create app in mock mode (no external dependencies required)

```bash
AZURE_CONFIG_DIR=$(pwd)/.azure-config az containerapp create \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --environment ca-cdpmerged-fast-env \
  --image <acr_name>.azurecr.io/cdp-merged:mock-<tag> \
  --ingress external \
  --target-port 8000 \
  --min-replicas 1 \
  --registry-server <acr_name>.azurecr.io \
  --registry-username <acr_name> \
  --registry-password <acr_password> \
  --secrets openai-api-key=mock-key tracardi-password=<redacted> \
  --env-vars \
    LLM_PROVIDER=mock \
    LOG_LEVEL=INFO \
    DEBUG=false \
    CHAINLIT_PORT=8000 \
    TRACARDI_API_URL=http://localhost:8686 \
    TRACARDI_SOURCE_ID=kbo-source \
    TRACARDI_USERNAME=admin \
    TRACARDI_PASSWORD=secretref:tracardi-password \
    OPENAI_API_KEY=secretref:openai-api-key
```

### 5. Verify deployment

```bash
AZURE_CONFIG_DIR=$(pwd)/.azure-config az containerapp show -n ca-cdpmerged-fast -g rg-cdpmerged-fast \
  --query '{fqdn:properties.configuration.ingress.fqdn,state:properties.runningStatus}' -o json
curl -i https://<fqdn>/
```

---

## Production Deployment

### Environment Variables

Set these secrets securely (never commit to Git):

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | LLM API key |
| `TRACARDI_PASSWORD` | Tracardi admin password |
| `FLEXMAIL_API_TOKEN` | Flexmail API token |
| `FLEXMAIL_WEBHOOK_SECRET` | HMAC webhook secret |

Use Docker secrets or a secrets manager (Vault, AWS Secrets Manager):

```yaml
# In docker-compose.prod.yml
services:
  app:
    environment:
      OPENAI_API_KEY: /run/secrets/openai_key
    secrets:
      - openai_key
secrets:
  openai_key:
    external: true
```

### Health Checks

The application exposes a Prometheus metrics endpoint:

```bash
# Start metrics server (port 9090)
# Set in app startup if ENABLE_METRICS=true

# Check health (once /health route is added)
curl http://localhost:9090/metrics
```

### Kubernetes (Optional)

Key Kubernetes resources needed:
- `Deployment` for the app container
- `ConfigMap` for non-secret environment variables
- `Secret` for API keys
- `Service` + `Ingress` for external access
- `HorizontalPodAutoscaler` for auto-scaling

### Monitoring Alerts

Configure alerts for:

| Alert | Condition | Severity |
|---|---|---|
| High error rate | `cdp_errors_total` rate > 5/min | Critical |
| Slow queries | `cdp_query_duration_seconds` p95 > 10s | Warning |
| LLM failures | `cdp_llm_requests_total{status="error"}` > 3/min | Critical |
| Tracardi down | Tracardi health check fails | Critical |
| Flexmail sync failures | `cdp_flexmail_push_total{status="error"}` > 0 | Warning |
