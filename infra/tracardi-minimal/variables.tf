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
  description = "Linux admin user for VM."
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
  default     = "78.21.222.70/32"
}

variable "office_allowed_cidr" {
  description = "Office/VPN CIDR allowed for Tracardi API/GUI public access."
  type        = string
  default     = "78.21.222.70/32"
}

variable "webhook_allowed_cidrs" {
  description = "CIDRs allowed to send webhooks (ports 80, 443)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "vnet_cidr" {
  description = "Address space for the Tracardi VNet."
  type        = string
  default     = "10.57.0.0/16"
}

variable "subnet_cidr" {
  description = "Subnet CIDR for Tracardi VM."
  type        = string
  default     = "10.57.1.0/24"
}

variable "vm_size" {
  description = "Size for Tracardi VM (Phase 1 minimal)."
  type        = string
  default     = "Standard_B1ms"
}

variable "os_disk_size_gb" {
  description = "OS disk size in GB."
  type        = number
  default     = 32
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

variable "mysql_image" {
  description = "Container image for MySQL."
  type        = string
  default     = "mysql:8.0"
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

variable "mysql_password" {
  description = "Optional override for MySQL root password."
  type        = string
  default     = ""
  sensitive   = true
}

variable "tags" {
  description = "Additional tags for all resources."
  type        = map(string)
  default = {
    workload    = "tracardi"
    managed     = "terraform"
    component   = "eventhub"
    cost_center = "cdp"
    temporary   = "false"
  }
}
