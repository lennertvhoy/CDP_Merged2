# Tracardi Option B Stack (B2s + B1ms)

This stack provisions the architecture recommended in the deployment spec:

- `Standard_B2s` VM: Tracardi API + Tracardi GUI
- `Standard_B1ms` VM: Elasticsearch + Redis
- Blob storage container for Elasticsearch snapshots
- NSGs locked to office CIDR and Container App subnet CIDR

## Estimated Cost (West Europe)

- `Standard_B2s` VM: ~EUR 35/month
- `Standard_B1ms` VM: ~EUR 13/month
- Storage + network baseline: ~EUR 5-10/month
- Total for this stack: ~EUR 53-58/month

Combined with existing Container App and Azure OpenAI usage, this remains near the EUR 55-100 target range (usage dependent).

## Files

- `cloud-init/tracardi-vm.yaml.tftpl`: Docker + compose + Tracardi API/GUI bootstrapping
- `cloud-init/data-vm.yaml.tftpl`: Docker + compose + Elasticsearch/Redis bootstrapping
- `scripts/tf.sh`: Terraform helper script for this stack only
- `scripts/azure_openai.sh`: Azure OpenAI account + deployment commands
- `scripts/update_containerapp.sh`: Container App env/secrets update commands

## Prerequisites

1. Azure CLI logged in with target subscription
2. Terraform >= 1.6
3. Existing resource group `rg-cdpmerged-fast` (or set `create_resource_group=true`)
4. Office/VPN CIDR and Container App subnet CIDR identified

## Dry-run First (No Billable Changes)

```bash
export AZURE_CONFIG_DIR=/home/ff/Documents/CDP_Merged/.azure-config
az account set --subscription ed9400bc-d5eb-4aa6-8b3f-2d4c11b17b9f

cd infra/tracardi
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

./scripts/tf.sh init
./scripts/tf.sh plan -var-file=terraform.tfvars
```

Discover `container_app_subnet_cidr` from the existing Container App environment:

```bash
ENV_ID="$(az containerapp show -n ca-cdpmerged-fast -g rg-cdpmerged-fast --query properties.environmentId -o tsv)"
INFRA_SUBNET_ID="$(az containerapp env show --ids "${ENV_ID}" --query properties.vnetConfiguration.infrastructureSubnetId -o tsv)"
az network vnet subnet show --ids "${INFRA_SUBNET_ID}" --query addressPrefix -o tsv
```

If `infrastructureSubnetId` is `null`, your Container App environment is not VNet-integrated; create a VNet-integrated environment first, then use that subnet CIDR in `terraform.tfvars`.

## Apply (Only After Explicit Go-Ahead)

```bash
./scripts/tf.sh apply -var-file=terraform.tfvars
./scripts/tf.sh output
```

## Azure OpenAI Commands

```bash
./scripts/azure_openai.sh print
# After approval:
./scripts/azure_openai.sh create
./scripts/azure_openai.sh deploy
./scripts/azure_openai.sh show
```

`show` prints:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT_NAME` (primary)
- `AZURE_OPENAI_DEPLOYMENT` (legacy alias)
- `AZURE_OPENAI_API_KEY`

## Container App Integration Commands

```bash
./scripts/update_containerapp.sh print
# After approval and with real values exported:
./scripts/update_containerapp.sh apply
```
