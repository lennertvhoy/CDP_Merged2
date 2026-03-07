# Additional Variables for Cost Optimization
# Add these to your existing variables.tf file

# =============================================================================
# CONTAINER APP SCALING VARIABLES
# =============================================================================

variable "container_app_cpu" {
  description = "CPU allocation for Container App (0.25, 0.5, 0.75, 1.0, etc.)"
  type        = number
  default     = 0.5

  validation {
    condition     = var.container_app_cpu >= 0.25 && var.container_app_cpu <= 2.0
    error_message = "Container App CPU must be between 0.25 and 2.0 vCPU."
  }
}

variable "container_app_memory" {
  description = "Memory allocation for Container App (GiB)"
  type        = string
  default     = "1Gi"

  validation {
    condition     = can(regex("^[0-9]+(\\.[0-9]+)?Gi$", var.container_app_memory))
    error_message = "Memory must be specified in GiB format (e.g., '0.5Gi', '1Gi', '2Gi')."
  }
}

variable "container_app_min_replicas" {
  description = "Minimum number of replicas for Container App (0 for scale-to-zero)"
  type        = number
  default     = 1
}

variable "container_app_max_replicas" {
  description = "Maximum number of replicas for Container App"
  type        = number
  default     = 10
}

variable "aca_environment_type" {
  description = "Container App Environment type (Consumption or Premium)"
  type        = string
  default     = "Consumption"
}

# =============================================================================
# LOG ANALYTICS VARIABLES
# =============================================================================

variable "log_analytics_sku" {
  description = "SKU for Log Analytics workspace"
  type        = string
  default     = "PerGB2018"
}

variable "log_analytics_retention_days" {
  description = "Retention period for Log Analytics data in days"
  type        = number
  default     = 30
}

variable "log_analytics_workspace_name" {
  description = "Explicit name for Log Analytics workspace to prevent duplicates"
  type        = string
  default     = "" # If empty, use generated name
}

# =============================================================================
# STORAGE VARIABLES
# =============================================================================

variable "storage_container_soft_delete_days" {
  description = "Number of days to retain deleted container blobs"
  type        = number
  default     = 7
}

# =============================================================================
# NETWORKING VARIABLES
# =============================================================================

variable "public_ip_sku" {
  description = "SKU for Public IP (Basic or Standard)"
  type        = string
  default     = "Standard"

  validation {
    condition     = contains(["Basic", "Standard"], var.public_ip_sku)
    error_message = "Public IP SKU must be Basic or Standard."
  }
}

# =============================================================================
# COST OPTIMIZATION FEATURE FLAGS
# =============================================================================

variable "enable_auto_shutdown" {
  description = "Enable automatic shutdown of dev resources during off-hours"
  type        = bool
  default     = false
}

variable "auto_shutdown_time" {
  description = "UTC time to automatically shutdown dev VMs (HHmm format)"
  type        = string
  default     = "1900" # 7 PM UTC
}

variable "auto_startup_time" {
  description = "UTC time to automatically startup dev VMs (HHmm format)"
  type        = string
  default     = "0700" # 7 AM UTC
}

variable "enable_budget_alerts" {
  description = "Enable Azure Cost Management budget alerts"
  type        = bool
  default     = false
}

variable "monthly_budget_amount" {
  description = "Monthly budget amount in EUR for cost alerts"
  type        = number
  default     = 100
}

variable "budget_alert_email" {
  description = "Email address for budget alerts"
  type        = string
  default     = ""
}

variable "monthly_budget_eur" {
  description = "Monthly budget in EUR"
  type        = number
  default     = 200
}

variable "enable_container_app" {
  description = "Enable Container App deployment"
  type        = bool
  default     = false
}
