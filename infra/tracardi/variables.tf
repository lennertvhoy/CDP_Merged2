variable "project_name" {
  description = "Project slug used in Azure resource names."
  type        = string
  default     = "cdpmerged"
}

variable "environment" {
  description = "Environment name appended to resources."
  type        = string
  default     = "prod"
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "westeurope"
}

variable "resource_group_name" {
  description = "Target resource group for Tracardi resources."
  type        = string
  default     = "rg-cdpmerged-fast"
}

variable "create_resource_group" {
  description = "Set true only if Terraform should create the resource group."
  type        = bool
  default     = false
}

variable "admin_username" {
  description = "Linux admin user for both VMs."
  type        = string
  default     = "azureuser"
}

variable "admin_ssh_public_key" {
  description = "SSH RSA public key content for VM login."
  type        = string
}

variable "admin_allowed_cidr" {
  description = "Office/VPN CIDR allowed for SSH access (port 22)."
  type        = string
}

variable "office_allowed_cidr" {
  description = "Office/VPN CIDR allowed for Tracardi API/GUI public access."
  type        = string
}

variable "container_app_subnet_cidr" {
  description = "CIDR of the CDP_Merged Container App subnet that can reach 8686/9200/6379."
  type        = string
}

variable "vnet_cidr" {
  description = "Address space for the Tracardi VNet."
  type        = string
  default     = "10.56.0.0/16"
}

variable "tracardi_subnet_cidr" {
  description = "Subnet CIDR for Tracardi API/GUI VM."
  type        = string
  default     = "10.56.1.0/24"
}

variable "data_subnet_cidr" {
  description = "Subnet CIDR for Elasticsearch/Redis VM."
  type        = string
  default     = "10.56.2.0/24"
}

variable "data_private_ip" {
  description = "Static private IP for the Elasticsearch/Redis VM."
  type        = string
  default     = "10.56.2.10"
}

variable "tracardi_vm_size" {
  description = "Size for Tracardi API/GUI VM (Option B default)."
  type        = string
  default     = "Standard_B2s"
}

variable "data_vm_size" {
  description = "Size for Elasticsearch/Redis VM (Option B default)."
  type        = string
  default     = "Standard_B1ms"
}

variable "tracardi_api_image" {
  description = "Container image for Tracardi API."
  type        = string
  default     = "tracardi/tracardi-api:1.0.0"
}

variable "tracardi_gui_image" {
  description = "Container image for Tracardi GUI."
  type        = string
  default     = "tracardi/tracardi-gui:1.0.0"
}

variable "elasticsearch_image" {
  description = "Container image for Elasticsearch."
  type        = string
  default     = "docker.elastic.co/elasticsearch/elasticsearch:8.11.0"
}

variable "redis_image" {
  description = "Container image for Redis."
  type        = string
  default     = "redis:7-alpine"
}

variable "mysql_image" {
  description = "Container image for MySQL."
  type        = string
  default     = "mysql:8.0"
}

variable "elasticsearch_heap_mb" {
  description = "Heap size for Elasticsearch in MB."
  type        = number
  default     = 1024
}

variable "tracardi_admin_password" {
  description = "Optional override for Tracardi admin password."
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

variable "redis_password" {
  description = "Optional override for Redis password."
  type        = string
  default     = ""
  sensitive   = true
}

variable "mysql_password" {
  description = "Optional override for MySQL root password used by local Tracardi VM MySQL."
  type        = string
  default     = ""
  sensitive   = true
}

variable "storage_account_tier" {
  description = "Tier for snapshot storage account."
  type        = string
  default     = "Standard"
}

variable "storage_replication_type" {
  description = "Replication for snapshot storage account."
  type        = string
  default     = "LRS"
}

variable "tags" {
  description = "Additional tags for all resources."
  type        = map(string)
  default = {
    workload = "tracardi"
    managed  = "terraform"
  }
}
