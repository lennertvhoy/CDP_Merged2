variable "project_name" {
  description = "Project slug used in resource names."
  type        = string
  default     = "cdpmerged"
}

variable "environment" {
  description = "Environment name (dev/stage/prod)."
  type        = string
  default     = "prod"
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "westeurope"
}

variable "resource_group_name" {
  description = "Optional override for the resource group name."
  type        = string
  default     = ""
}

variable "admin_username" {
  description = "Admin username for Linux VMs."
  type        = string
  default     = "azureuser"
}

variable "admin_ssh_public_key" {
  description = "SSH public key content used to access the VMs."
  type        = string
}

variable "admin_allowed_cidr" {
  description = "CIDR that can SSH into VMs."
  type        = string
  default     = "0.0.0.0/0"
}

variable "app_allowed_cidr" {
  description = "CIDR allowed to reach Chainlit/Tracardi public ports."
  type        = string
  default     = "0.0.0.0/0"
}

variable "app_vm_size" {
  description = "Azure size for the app VM (hosts Tracardi/API/MySQL/RabbitMQ/agent)."
  type        = string
  default     = "Standard_B2s"
}

variable "es_vm_size" {
  description = "Azure size for the Elasticsearch VM."
  type        = string
  default     = "Standard_B1ms"
}

variable "elasticsearch_private_ip" {
  description = "Static private IP assigned to Elasticsearch VM NIC."
  type        = string
  default     = "10.42.2.10"
}

variable "elasticsearch_heap_mb" {
  description = "JVM heap for Elasticsearch container in MB."
  type        = number
  default     = 1024
}

variable "agent_image" {
  description = "Prebuilt container image for this repository app."
  type        = string
  default     = "ghcr.io/your-org/cdp-merged:latest"
}

variable "tracardi_api_image" {
  description = "Tracardi API container image."
  type        = string
  default     = "tracardi/tracardi-api:1.0.0"
}

variable "tracardi_gui_image" {
  description = "Tracardi GUI container image."
  type        = string
  default     = "tracardi/tracardi-gui:1.0.0"
}

variable "mysql_image" {
  description = "MySQL container image."
  type        = string
  default     = "mysql:8.0"
}

variable "rabbitmq_image" {
  description = "RabbitMQ container image."
  type        = string
  default     = "rabbitmq:3.13-management"
}

variable "llm_provider" {
  description = "LLM provider exposed to the agent app."
  type        = string
  default     = "openai"
}

variable "enable_azure_search" {
  description = "Create an Azure AI Search service for the runtime (disabled by default for phased rollout)."
  type        = bool
  default     = false
}

variable "azure_search_service_name" {
  description = "Optional Azure AI Search service name override. When empty and enabled, a deterministic name is generated."
  type        = string
  default     = ""
}

variable "azure_search_sku" {
  description = "Azure AI Search SKU."
  type        = string
  default     = "basic"
}

variable "azure_search_replica_count" {
  description = "Replica count for Azure AI Search service."
  type        = number
  default     = 1
}

variable "azure_search_partition_count" {
  description = "Partition count for Azure AI Search service."
  type        = number
  default     = 1
}

variable "azure_search_public_network_access_enabled" {
  description = "Allow public network access to Azure AI Search service endpoint."
  type        = bool
  default     = true
}

variable "azure_search_local_authentication_enabled" {
  description = "Enable query/admin key authentication on Azure AI Search service (keep true for phased migration fallback)."
  type        = bool
  default     = true
}

variable "azure_search_endpoint" {
  description = "Optional external Azure AI Search endpoint used when service provisioning is disabled."
  type        = string
  default     = ""
}

variable "azure_search_index_name" {
  description = "Azure AI Search index name used by the app runtime."
  type        = string
  default     = "cdp-documents"
}

variable "azure_search_api_version" {
  description = "Azure AI Search REST API version used by runtime."
  type        = string
  default     = "2023-11-01"
}

variable "azure_search_top_k" {
  description = "Default top-k retrieval size for Azure AI Search runtime queries."
  type        = number
  default     = 20
}

variable "azure_search_timeout_seconds" {
  description = "Default HTTP timeout (seconds) for Azure AI Search runtime calls."
  type        = number
  default     = 10
}

variable "azure_search_id_field" {
  description = "Azure AI Search document id field name."
  type        = string
  default     = "id"
}

variable "azure_search_title_field" {
  description = "Azure AI Search title field name."
  type        = string
  default     = "name"
}

variable "azure_search_content_field" {
  description = "Azure AI Search content field name."
  type        = string
  default     = "content"
}

variable "azure_search_url_field" {
  description = "Azure AI Search source URL field name."
  type        = string
  default     = "source_url"
}

variable "azure_auth_use_default_credential" {
  description = "Expose AZURE_AUTH_USE_DEFAULT_CREDENTIAL for MI-first auth resolution."
  type        = bool
  default     = true
}

variable "azure_auth_allow_key_fallback" {
  description = "Expose AZURE_AUTH_ALLOW_KEY_FALLBACK for phased rollout compatibility."
  type        = bool
  default     = true
}

variable "azure_auth_strict_mi_kv_only" {
  description = "Expose AZURE_AUTH_STRICT_MI_KV_ONLY to enforce strict MI/KV auth path."
  type        = bool
  default     = false
}

variable "azure_key_vault_url" {
  description = "Optional Azure Key Vault URL used by runtime to resolve API-key secrets."
  type        = string
  default     = ""
}

variable "azure_key_vault_id" {
  description = "Optional Key Vault resource ID for assigning app VM managed identity access (Secrets User role)."
  type        = string
  default     = ""
}

variable "azure_search_api_key_secret_name" {
  description = "Optional Key Vault secret name containing Azure AI Search API key."
  type        = string
  default     = ""
}

variable "azure_search_api_key" {
  description = "Optional explicit Azure AI Search API key for fallback auth path."
  type        = string
  default     = ""
  sensitive   = true
}

variable "azure_search_inject_admin_key" {
  description = "When true and Azure Search is provisioned, inject generated admin key into runtime env (defaults false for safer rollout)."
  type        = bool
  default     = false
}

variable "enable_azure_search_retrieval" {
  description = "Expose ENABLE_AZURE_SEARCH_RETRIEVAL feature flag to runtime."
  type        = bool
  default     = false
}

variable "enable_azure_search_shadow_mode" {
  description = "Expose ENABLE_AZURE_SEARCH_SHADOW_MODE feature flag to runtime."
  type        = bool
  default     = false
}

variable "enable_citation_required" {
  description = "Expose ENABLE_CITATION_REQUIRED feature flag to runtime."
  type        = bool
  default     = false
}

variable "agent_environment" {
  description = "Extra environment variables injected in the agent container (supports secret values; marked sensitive)."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "tracardi_admin_password" {
  description = "Optional override for Tracardi admin password."
  type        = string
  default     = ""
  sensitive   = true
}

variable "mysql_password" {
  description = "Optional override for MySQL password."
  type        = string
  default     = ""
  sensitive   = true
}

variable "installation_token" {
  description = "Optional override for Tracardi INSTALLATION_TOKEN."
  type        = string
  default     = ""
  sensitive   = true
}

variable "tags" {
  description = "Extra tags applied to all resources."
  type        = map(string)
  default = {
    workload = "cdp"
    managed  = "terraform"
  }
}
