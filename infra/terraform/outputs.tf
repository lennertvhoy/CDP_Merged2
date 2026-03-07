output "subscription_id" {
  description = "Active subscription id used by Azure CLI/provider."
  value       = data.azurerm_client_config.current.subscription_id
}

output "resource_group_name" {
  description = "Resource group hosting the CDP stack."
  value       = azurerm_resource_group.cdp.name
}

output "app_public_ip" {
  description = "Public IP address of the app VM."
  value       = azurerm_public_ip.app.ip_address
}

output "chainlit_url" {
  description = "Chainlit UI URL."
  value       = "http://${azurerm_public_ip.app.ip_address}:8000"
}

output "tracardi_api_url" {
  description = "Tracardi API URL."
  value       = "http://${azurerm_public_ip.app.ip_address}:8686"
}

output "tracardi_gui_url" {
  description = "Tracardi GUI URL."
  value       = "http://${azurerm_public_ip.app.ip_address}:8787"
}

output "elasticsearch_private_endpoint" {
  description = "Private Elasticsearch endpoint reachable from app subnet only."
  value       = "http://${var.elasticsearch_private_ip}:9200"
}

output "redis_hostname" {
  description = "Azure Redis host."
  value       = azurerm_redis_cache.cache.hostname
}

output "redis_port" {
  description = "Azure Redis non-SSL port configured for Tracardi compatibility."
  value       = 6379
}

output "eventhub_namespace" {
  description = "Event Hubs namespace name."
  value       = azurerm_eventhub_namespace.cdp.name
}

output "eventhub_name" {
  description = "Event Hub entity name."
  value       = azurerm_eventhub.events.name
}

output "eventhub_connection_string" {
  description = "Namespace-level connection string for app producers/consumers."
  value       = azurerm_eventhub_namespace_authorization_rule.agent.primary_connection_string
  sensitive   = true
}

output "storage_account_name" {
  description = "Storage account for snapshots/backups."
  value       = azurerm_storage_account.cdp.name
}

output "storage_container_name" {
  description = "Blob container used for Elasticsearch snapshots."
  value       = azurerm_storage_container.es_snapshots.name
}

output "application_insights_connection_string" {
  description = "Application Insights connection string."
  value       = azurerm_application_insights.cdp.connection_string
  sensitive   = true
}

output "azure_search_enabled" {
  description = "Whether Azure AI Search service provisioning is enabled in this stack."
  value       = var.enable_azure_search
}

output "azure_search_service_name" {
  description = "Azure AI Search service name when provisioned; null when disabled."
  value       = var.enable_azure_search ? azurerm_search_service.cdp[0].name : null
}

output "azure_search_endpoint" {
  description = "Effective Azure AI Search endpoint injected into runtime configuration."
  value       = local.azure_search_endpoint
}

output "azure_search_index_name" {
  description = "Azure AI Search index name used by runtime."
  value       = var.azure_search_index_name
}

output "azure_search_runtime_settings" {
  description = "Non-secret Azure Search runtime settings passed to the app."
  value = {
    AZURE_SEARCH_API_VERSION          = var.azure_search_api_version
    AZURE_SEARCH_TOP_K                = tostring(var.azure_search_top_k)
    AZURE_SEARCH_TIMEOUT_SECONDS      = tostring(var.azure_search_timeout_seconds)
    AZURE_SEARCH_ID_FIELD             = var.azure_search_id_field
    AZURE_SEARCH_TITLE_FIELD          = var.azure_search_title_field
    AZURE_SEARCH_CONTENT_FIELD        = var.azure_search_content_field
    AZURE_SEARCH_URL_FIELD            = var.azure_search_url_field
    ENABLE_AZURE_SEARCH_RETRIEVAL     = tostring(var.enable_azure_search_retrieval)
    ENABLE_AZURE_SEARCH_SHADOW_MODE   = tostring(var.enable_azure_search_shadow_mode)
    ENABLE_CITATION_REQUIRED          = tostring(var.enable_citation_required)
    AZURE_AUTH_USE_DEFAULT_CREDENTIAL = tostring(var.azure_auth_use_default_credential)
    AZURE_AUTH_ALLOW_KEY_FALLBACK     = tostring(var.azure_auth_allow_key_fallback)
    AZURE_AUTH_STRICT_MI_KV_ONLY      = tostring(var.azure_auth_strict_mi_kv_only)
    AZURE_KEY_VAULT_URL               = var.azure_key_vault_url
    AZURE_SEARCH_API_KEY_SECRET_NAME  = var.azure_search_api_key_secret_name
  }
}

output "app_managed_identity_principal_id" {
  description = "System-assigned managed identity principal id of the app VM."
  value       = azurerm_linux_virtual_machine.app.identity[0].principal_id
}

output "azure_search_api_key_effective" {
  description = "Effective Azure Search API key value injected into runtime (explicit or generated, may be empty)."
  value       = local.azure_search_api_key_effective
  sensitive   = true
}

output "mysql_password" {
  description = "MySQL password used by Tracardi (generated when not supplied)."
  value       = local.effective_mysql_password
  sensitive   = true
}

output "tracardi_admin_password" {
  description = "Tracardi admin password (generated when not supplied)."
  value       = local.effective_tracardi_password
  sensitive   = true
}

output "tracardi_installation_token" {
  description = "Tracardi installation token (generated when not supplied)."
  value       = local.effective_installation_token
  sensitive   = true
}

# PostgreSQL Outputs
output "postgresql_server_name" {
  description = "Azure PostgreSQL Flexible Server name."
  value       = azurerm_postgresql_flexible_server.cdp.name
}

output "postgresql_server_fqdn" {
  description = "Fully qualified domain name of the PostgreSQL server."
  value       = azurerm_postgresql_flexible_server.cdp.fqdn
}

output "postgresql_database_name" {
  description = "Name of the PostgreSQL database."
  value       = azurerm_postgresql_flexible_server_database.cdp.name
}

output "postgresql_admin_username" {
  description = "PostgreSQL administrator username."
  value       = azurerm_postgresql_flexible_server.cdp.administrator_login
}

output "postgresql_admin_password" {
  description = "PostgreSQL administrator password."
  value       = local.effective_postgresql_password
  sensitive   = true
}

output "postgresql_connection_string" {
  description = "PostgreSQL connection string for application use."
  value       = "postgresql://${azurerm_postgresql_flexible_server.cdp.administrator_login}:${local.effective_postgresql_password}@${azurerm_postgresql_flexible_server.cdp.fqdn}:5432/${azurerm_postgresql_flexible_server_database.cdp.name}?sslmode=require"
  sensitive   = true
}
