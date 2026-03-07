# --------------------------------------------------------------------------
# PostgreSQL Flexible Server
# --------------------------------------------------------------------------
# Manages the canonical customer-intelligence truth layer.
# Import: terraform import azurerm_postgresql_flexible_server.this <resource-id>
# --------------------------------------------------------------------------

resource "azurerm_postgresql_flexible_server" "this" {
  name                          = var.postgres_server_name
  resource_group_name           = local.rg_name
  location                      = var.postgres_location
  version                       = "15"
  administrator_login           = var.postgres_admin_login
  administrator_password        = var.postgres_admin_password
  sku_name                      = var.postgres_sku
  storage_mb                    = var.postgres_storage_mb
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false
  auto_grow_enabled             = false
  public_network_access_enabled = true
  zone                          = var.postgres_zone

  tags = local.common_tags

  lifecycle {
    # Prevent accidental deletion of the database
    prevent_destroy = true
  }
}

# Firewall rule: allow access from office/dev IP
resource "azurerm_postgresql_flexible_server_firewall_rule" "client" {
  name             = "AllowClientIP"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = var.postgres_allowed_ip
  end_ip_address   = var.postgres_allowed_ip
}

# Firewall rule: allow Azure services
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}
