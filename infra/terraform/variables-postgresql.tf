# Azure PostgreSQL Flexible Server Variables

variable "postgresql_admin_password" {
  description = "Optional override for PostgreSQL admin password. If empty, a random password is generated."
  type        = string
  default     = ""
  sensitive   = true
}

variable "postgresql_sku_name" {
  description = "SKU name for Azure PostgreSQL Flexible Server. B_Standard_B2s for dev/test, GP_Standard_D2s_v3 for production."
  type        = string
  default     = "B_Standard_B2s"
}

variable "postgresql_storage_mb" {
  description = "Storage size in MB for PostgreSQL server. 32768 = 32GB."
  type        = number
  default     = 32768
}

variable "postgresql_database_name" {
  description = "Name of the PostgreSQL database to create."
  type        = string
  default     = "cdp"
}

variable "postgresql_backup_retention_days" {
  description = "Backup retention period in days."
  type        = number
  default     = 7
}

variable "postgresql_geo_redundant_backup_enabled" {
  description = "Enable geo-redundant backups."
  type        = bool
  default     = false
}
