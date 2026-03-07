resource "random_string" "suffix" {
  length  = 4
  lower   = true
  upper   = false
  numeric = true
  special = false
}

resource "random_password" "tracardi_admin" {
  length           = 20
  special          = true
  override_special = "!@%^*-_"
}

resource "random_password" "mysql" {
  length           = 20
  special          = true
  override_special = "!@%^*-_"
}

resource "random_password" "installation_token" {
  length  = 32
  special = false
}

locals {
  name_token  = substr(lower(replace("${var.project_name}-${var.environment}", "/[^a-z0-9-]/", "")), 0, 32)
  alnum_token = substr(lower(replace("${var.project_name}${var.environment}", "/[^a-z0-9]/", "")), 0, 12)

  resource_group_name = var.resource_group_name != "" ? var.resource_group_name : "rg-${local.name_token}"
  common_tags         = merge(var.tags, { project = var.project_name, environment = var.environment })

  effective_tracardi_password  = var.tracardi_admin_password != "" ? var.tracardi_admin_password : random_password.tracardi_admin.result
  effective_mysql_password     = var.mysql_password != "" ? var.mysql_password : random_password.mysql.result
  effective_installation_token = var.installation_token != "" ? var.installation_token : random_password.installation_token.result

  azure_search_service_name = var.azure_search_service_name != "" ? var.azure_search_service_name : substr("srch-${local.name_token}-${random_string.suffix.result}", 0, 60)
  azure_search_endpoint     = var.enable_azure_search ? "https://${azurerm_search_service.cdp[0].name}.search.windows.net" : var.azure_search_endpoint
  azure_search_api_key_effective = var.azure_search_api_key != "" ? var.azure_search_api_key : (
    var.enable_azure_search && var.azure_search_inject_admin_key && var.azure_search_local_authentication_enabled
    ? azurerm_search_service.cdp[0].primary_key
    : ""
  )

  redis_port = 6379

  agent_env = merge(
    {
      LLM_PROVIDER                           = var.llm_provider
      TRACARDI_API_URL                       = "http://tracardi-api:80"
      ELASTICSEARCH_URL                      = "http://${var.elasticsearch_private_ip}:9200"
      EVENTHUB_NAMESPACE                     = azurerm_eventhub_namespace.cdp.name
      EVENTHUB_NAME                          = azurerm_eventhub.events.name
      EVENTHUB_CONNECTION_STRING             = azurerm_eventhub_namespace_authorization_rule.agent.primary_connection_string
      REDIS_HOST                             = azurerm_redis_cache.cache.hostname
      REDIS_PORT                             = tostring(local.redis_port)
      REDIS_PASSWORD                         = azurerm_redis_cache.cache.primary_access_key
      APPLICATIONINSIGHTS_CONNECTION_STRING  = azurerm_application_insights.cdp.connection_string
      APPLICATIONINSIGHTS_INSTRUMENTATIONKEY = azurerm_application_insights.cdp.instrumentation_key
      AZURE_EVENTHUBS_CONNECTION_STRING      = azurerm_eventhub_namespace_authorization_rule.agent.primary_connection_string
      AZURE_EVENTHUBS_NAME                   = azurerm_eventhub.events.name
      AZURE_EVENTHUBS_NAMESPACE              = azurerm_eventhub_namespace.cdp.name
      ENABLE_AZURE_SEARCH_RETRIEVAL          = tostring(var.enable_azure_search_retrieval)
      ENABLE_AZURE_SEARCH_SHADOW_MODE        = tostring(var.enable_azure_search_shadow_mode)
      ENABLE_CITATION_REQUIRED               = tostring(var.enable_citation_required)
      AZURE_SEARCH_ENDPOINT                  = local.azure_search_endpoint
      AZURE_SEARCH_INDEX_NAME                = var.azure_search_index_name
      AZURE_SEARCH_API_VERSION               = var.azure_search_api_version
      AZURE_SEARCH_TOP_K                     = tostring(var.azure_search_top_k)
      AZURE_SEARCH_TIMEOUT_SECONDS           = tostring(var.azure_search_timeout_seconds)
      AZURE_SEARCH_ID_FIELD                  = var.azure_search_id_field
      AZURE_SEARCH_TITLE_FIELD               = var.azure_search_title_field
      AZURE_SEARCH_CONTENT_FIELD             = var.azure_search_content_field
      AZURE_SEARCH_URL_FIELD                 = var.azure_search_url_field
      AZURE_AUTH_USE_DEFAULT_CREDENTIAL      = tostring(var.azure_auth_use_default_credential)
      AZURE_AUTH_ALLOW_KEY_FALLBACK          = tostring(var.azure_auth_allow_key_fallback)
      AZURE_AUTH_STRICT_MI_KV_ONLY           = tostring(var.azure_auth_strict_mi_kv_only)
      AZURE_KEY_VAULT_URL                    = var.azure_key_vault_url
      AZURE_SEARCH_API_KEY_SECRET_NAME       = var.azure_search_api_key_secret_name
      AZURE_SEARCH_API_KEY                   = local.azure_search_api_key_effective
    },
    var.agent_environment
  )
}

resource "azurerm_resource_group" "cdp" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.common_tags
}

resource "azurerm_virtual_network" "cdp" {
  name                = "vnet-${local.name_token}"
  resource_group_name = azurerm_resource_group.cdp.name
  location            = azurerm_resource_group.cdp.location
  address_space       = ["10.42.0.0/16"]
  tags                = local.common_tags
}

resource "azurerm_network_security_group" "app" {
  name                = "nsg-app-${local.name_token}"
  location            = azurerm_resource_group.cdp.location
  resource_group_name = azurerm_resource_group.cdp.name
  tags                = local.common_tags
}

resource "azurerm_network_security_rule" "app_ssh" {
  name                        = "allow-ssh"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefix       = var.admin_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.cdp.name
  network_security_group_name = azurerm_network_security_group.app.name
}

resource "azurerm_network_security_rule" "app_chainlit" {
  name                        = "allow-chainlit"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8000"
  source_address_prefix       = var.app_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.cdp.name
  network_security_group_name = azurerm_network_security_group.app.name
}

resource "azurerm_network_security_rule" "app_tracardi_api" {
  name                        = "allow-tracardi-api"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8686"
  source_address_prefix       = var.app_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.cdp.name
  network_security_group_name = azurerm_network_security_group.app.name
}

resource "azurerm_network_security_rule" "app_tracardi_gui" {
  name                        = "allow-tracardi-gui"
  priority                    = 130
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8787"
  source_address_prefix       = var.app_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.cdp.name
  network_security_group_name = azurerm_network_security_group.app.name
}

resource "azurerm_network_security_group" "data" {
  name                = "nsg-data-${local.name_token}"
  location            = azurerm_resource_group.cdp.location
  resource_group_name = azurerm_resource_group.cdp.name
  tags                = local.common_tags
}

resource "azurerm_network_security_rule" "data_ssh" {
  name                        = "allow-ssh"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefix       = var.admin_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.cdp.name
  network_security_group_name = azurerm_network_security_group.data.name
}

resource "azurerm_subnet" "app" {
  name                 = "snet-app"
  resource_group_name  = azurerm_resource_group.cdp.name
  virtual_network_name = azurerm_virtual_network.cdp.name
  address_prefixes     = ["10.42.1.0/24"]
}

resource "azurerm_subnet" "data" {
  name                 = "snet-data"
  resource_group_name  = azurerm_resource_group.cdp.name
  virtual_network_name = azurerm_virtual_network.cdp.name
  address_prefixes     = ["10.42.2.0/24"]
}

resource "azurerm_network_security_rule" "data_es_from_app" {
  name                        = "allow-elasticsearch-from-app"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "9200"
  source_address_prefix       = azurerm_subnet.app.address_prefixes[0]
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.cdp.name
  network_security_group_name = azurerm_network_security_group.data.name
}

resource "azurerm_subnet_network_security_group_association" "app" {
  subnet_id                 = azurerm_subnet.app.id
  network_security_group_id = azurerm_network_security_group.app.id
}

resource "azurerm_subnet_network_security_group_association" "data" {
  subnet_id                 = azurerm_subnet.data.id
  network_security_group_id = azurerm_network_security_group.data.id
}

resource "azurerm_public_ip" "app" {
  name                = "pip-app-${local.name_token}"
  location            = azurerm_resource_group.cdp.location
  resource_group_name = azurerm_resource_group.cdp.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.common_tags
}

resource "azurerm_network_interface" "app" {
  name                = "nic-app-${local.name_token}"
  location            = azurerm_resource_group.cdp.location
  resource_group_name = azurerm_resource_group.cdp.name

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.app.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.app.id
  }

  tags = local.common_tags
}

resource "azurerm_network_interface" "es" {
  name                = "nic-es-${local.name_token}"
  location            = azurerm_resource_group.cdp.location
  resource_group_name = azurerm_resource_group.cdp.name

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.data.id
    private_ip_address_allocation = "Static"
    private_ip_address            = var.elasticsearch_private_ip
  }

  tags = local.common_tags
}

resource "azurerm_log_analytics_workspace" "cdp" {
  name                = "law-${local.name_token}-${random_string.suffix.result}"
  location            = azurerm_resource_group.cdp.location
  resource_group_name = azurerm_resource_group.cdp.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.common_tags
}

resource "azurerm_application_insights" "cdp" {
  name                = "appi-${local.name_token}-${random_string.suffix.result}"
  location            = azurerm_resource_group.cdp.location
  resource_group_name = azurerm_resource_group.cdp.name
  workspace_id        = azurerm_log_analytics_workspace.cdp.id
  application_type    = "web"
  tags                = local.common_tags
}

resource "azurerm_storage_account" "cdp" {
  name                            = substr("st${local.alnum_token}${random_string.suffix.result}", 0, 24)
  resource_group_name             = azurerm_resource_group.cdp.name
  location                        = azurerm_resource_group.cdp.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  tags                            = local.common_tags
}

resource "azurerm_storage_container" "es_snapshots" {
  name                  = "es-snapshots"
  storage_account_name  = azurerm_storage_account.cdp.name
  container_access_type = "private"
}

resource "azurerm_redis_cache" "cache" {
  name                          = substr("redis-${local.name_token}-${random_string.suffix.result}", 0, 63)
  location                      = azurerm_resource_group.cdp.location
  resource_group_name           = azurerm_resource_group.cdp.name
  capacity                      = 0
  family                        = "C"
  sku_name                      = "Basic"
  non_ssl_port_enabled          = true
  minimum_tls_version           = "1.2"
  public_network_access_enabled = true
  redis_version                 = "6"
  tags                          = local.common_tags
}

resource "azurerm_eventhub_namespace" "cdp" {
  name                = substr("evhns${local.alnum_token}${random_string.suffix.result}", 0, 50)
  location            = azurerm_resource_group.cdp.location
  resource_group_name = azurerm_resource_group.cdp.name
  sku                 = "Basic"
  capacity            = 1
  tags                = local.common_tags
}

resource "azurerm_eventhub" "events" {
  name                = "cdp-events"
  namespace_name      = azurerm_eventhub_namespace.cdp.name
  resource_group_name = azurerm_resource_group.cdp.name
  partition_count     = 2
  message_retention   = 1
}

resource "azurerm_eventhub_namespace_authorization_rule" "agent" {
  name                = "agent-access"
  namespace_name      = azurerm_eventhub_namespace.cdp.name
  resource_group_name = azurerm_resource_group.cdp.name
  listen              = true
  send                = true
  manage              = false
}

resource "azurerm_search_service" "cdp" {
  count = var.enable_azure_search ? 1 : 0

  name                = local.azure_search_service_name
  resource_group_name = azurerm_resource_group.cdp.name
  location            = azurerm_resource_group.cdp.location
  sku                 = var.azure_search_sku
  replica_count       = var.azure_search_replica_count
  partition_count     = var.azure_search_partition_count

  public_network_access_enabled = var.azure_search_public_network_access_enabled
  local_authentication_enabled  = var.azure_search_local_authentication_enabled
  tags                          = local.common_tags
}

resource "azurerm_role_assignment" "app_search_index_data_reader" {
  count = var.enable_azure_search ? 1 : 0

  scope                = azurerm_search_service.cdp[0].id
  role_definition_name = "Search Index Data Reader"
  principal_id         = azurerm_linux_virtual_machine.app.identity[0].principal_id
}

resource "azurerm_role_assignment" "app_key_vault_secrets_user" {
  count = var.azure_key_vault_id != "" ? 1 : 0

  scope                = var.azure_key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_virtual_machine.app.identity[0].principal_id
}

resource "azurerm_linux_virtual_machine" "elasticsearch" {
  name                = "vm-es-${local.name_token}"
  resource_group_name = azurerm_resource_group.cdp.name
  location            = azurerm_resource_group.cdp.location
  size                = var.es_vm_size
  admin_username      = var.admin_username

  network_interface_ids = [azurerm_network_interface.es.id]

  disable_password_authentication = true

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.admin_ssh_public_key
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  os_disk {
    name                 = "osdisk-es-${local.name_token}"
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 32
  }

  custom_data = base64encode(templatefile("${path.module}/cloud-init/es-vm.yaml.tftpl", {
    elasticsearch_heap_mb = var.elasticsearch_heap_mb
  }))

  tags = local.common_tags
}

resource "azurerm_linux_virtual_machine" "app" {
  name                = "vm-app-${local.name_token}"
  resource_group_name = azurerm_resource_group.cdp.name
  location            = azurerm_resource_group.cdp.location
  size                = var.app_vm_size
  admin_username      = var.admin_username

  network_interface_ids = [azurerm_network_interface.app.id]

  disable_password_authentication = true

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.admin_ssh_public_key
  }

  identity {
    type = "SystemAssigned"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  os_disk {
    name                 = "osdisk-app-${local.name_token}"
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 64
  }

  custom_data = base64encode(templatefile("${path.module}/cloud-init/app-vm.yaml.tftpl", {
    project_name            = var.project_name
    tracardi_api_image      = var.tracardi_api_image
    tracardi_gui_image      = var.tracardi_gui_image
    mysql_image             = var.mysql_image
    rabbitmq_image          = var.rabbitmq_image
    agent_image             = var.agent_image
    redis_host              = azurerm_redis_cache.cache.hostname
    redis_port              = local.redis_port
    redis_password          = azurerm_redis_cache.cache.primary_access_key
    elasticsearch_host      = var.elasticsearch_private_ip
    mysql_password          = local.effective_mysql_password
    tracardi_admin_password = local.effective_tracardi_password
    installation_token      = local.effective_installation_token
    agent_env               = local.agent_env
  }))

  tags = local.common_tags

  depends_on = [azurerm_linux_virtual_machine.elasticsearch]
}
