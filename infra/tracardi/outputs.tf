output "subscription_id" {
  description = "Active subscription id used by the Azure provider."
  value       = data.azurerm_client_config.current.subscription_id
}

output "resource_group_name" {
  description = "Resource group that hosts Tracardi resources."
  value       = local.rg_name
}

output "tracardi_public_ip" {
  description = "Public IP for Tracardi API/GUI VM."
  value       = azurerm_public_ip.tracardi.ip_address
}

output "tracardi_api_url" {
  description = "Tracardi API URL."
  value       = "http://${azurerm_public_ip.tracardi.ip_address}:8686"
}

output "tracardi_gui_url" {
  description = "Tracardi GUI URL."
  value       = "http://${azurerm_public_ip.tracardi.ip_address}:8787"
}

output "elasticsearch_connection_string" {
  description = "Private Elasticsearch endpoint for Tracardi and trusted sources."
  value       = "http://${var.data_private_ip}:9200"
}

output "redis_connection_string" {
  description = "Private Redis endpoint for Tracardi and trusted sources."
  value       = "redis://:${local.effective_redis_password}@${var.data_private_ip}:6379/0"
  sensitive   = true
}

output "storage_account_name" {
  description = "Storage account used for Elasticsearch snapshots."
  value       = azurerm_storage_account.tracardi.name
}

output "snapshot_container_name" {
  description = "Blob container name for Elasticsearch snapshots."
  value       = azurerm_storage_container.es_snapshots.name
}

output "snapshot_blob_container_url" {
  description = "HTTPS URL to the private snapshot container."
  value       = "https://${azurerm_storage_account.tracardi.name}.blob.core.windows.net/${azurerm_storage_container.es_snapshots.name}"
}

output "snapshot_storage_connection_string" {
  description = "Storage connection string for snapshot upload tooling."
  value       = azurerm_storage_account.tracardi.primary_connection_string
  sensitive   = true
}

output "tracardi_admin_password" {
  description = "Tracardi admin password (generated if not provided)."
  value       = local.effective_tracardi_password
  sensitive   = true
}

output "tracardi_installation_token" {
  description = "Tracardi installation token (generated if not provided)."
  value       = local.effective_installation_token
  sensitive   = true
}

output "redis_password" {
  description = "Redis password (generated if not provided)."
  value       = local.effective_redis_password
  sensitive   = true
}

output "mysql_password" {
  description = "MySQL root password used by the Tracardi VM local MySQL."
  value       = local.effective_mysql_password
  sensitive   = true
}
