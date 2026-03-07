# Azure PostgreSQL Flexible Server for CDP_Merged
# Provides managed PostgreSQL for KBO data import and enrichment

resource "random_password" "postgresql_admin" {
  length           = 20
  special          = true
  override_special = "!@#$%^&*-_"
}

locals {
  effective_postgresql_password = var.postgresql_admin_password != "" ? var.postgresql_admin_password : random_password.postgresql_admin.result
}

# Azure PostgreSQL Flexible Server
resource "azurerm_postgresql_flexible_server" "cdp" {
  name                   = "psql-${local.name_token}"
  resource_group_name    = azurerm_resource_group.cdp.name
  location               = azurerm_resource_group.cdp.location
  version                = "15"
  administrator_login    = "cdpadmin"
  administrator_password = local.effective_postgresql_password

  # SKU - B2s for development/testing, can scale up for production
  sku_name   = var.postgresql_sku_name
  storage_mb = var.postgresql_storage_mb

  # Backup configuration
  backup_retention_days        = var.postgresql_backup_retention_days
  geo_redundant_backup_enabled = var.postgresql_geo_redundant_backup_enabled

  # High availability (disabled for cost savings in dev/test)
  high_availability {
    mode = "SameZone"
  }

  # Maintenance window
  maintenance_window {
    day_of_week  = 0 # Sunday
    start_hour   = 3
    start_minute = 0
  }

  tags = local.common_tags

  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = false
  }
}

# PostgreSQL Database
resource "azurerm_postgresql_flexible_server_database" "cdp" {
  name      = var.postgresql_database_name
  server_id = azurerm_postgresql_flexible_server.cdp.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

# Firewall rule to allow Azure services
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.cdp.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Firewall rule to allow app VM subnet
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_app_vm" {
  name             = "AllowAppVM"
  server_id        = azurerm_postgresql_flexible_server.cdp.id
  start_ip_address = azurerm_public_ip.app.ip_address
  end_ip_address   = azurerm_public_ip.app.ip_address
}

# Enable required extensions
resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.cdp.id
  value     = "UUID_OSSP,PG_TRGM,PG_STAT_STATEMENTS"
}

# Connection pooling settings for high-throughput imports
resource "azurerm_postgresql_flexible_server_configuration" "max_connections" {
  name      = "max_connections"
  server_id = azurerm_postgresql_flexible_server.cdp.id
  value     = "200"
}

resource "azurerm_postgresql_flexible_server_configuration" "shared_buffers" {
  name      = "shared_buffers"
  server_id = azurerm_postgresql_flexible_server.cdp.id
  value     = "2097152" # 2GB in KB
}

resource "azurerm_postgresql_flexible_server_configuration" "effective_cache_size" {
  name      = "effective_cache_size"
  server_id = azurerm_postgresql_flexible_server.cdp.id
  value     = "6291456" # 6GB in KB
}

resource "azurerm_postgresql_flexible_server_configuration" "work_mem" {
  name      = "work_mem"
  server_id = azurerm_postgresql_flexible_server.cdp.id
  value     = "16384" # 16MB in KB
}

resource "azurerm_postgresql_flexible_server_configuration" "maintenance_work_mem" {
  name      = "maintenance_work_mem"
  server_id = azurerm_postgresql_flexible_server.cdp.id
  value     = "524288" # 512MB in KB
}
