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

resource "random_password" "installation_token" {
  length  = 32
  special = false
}

resource "random_password" "redis" {
  length           = 20
  special          = true
  override_special = "!@%^*-_"
}

resource "random_password" "mysql" {
  length           = 20
  special          = true
  override_special = "!@%^*-_"
}

locals {
  name_token = substr(lower(replace("${var.project_name}-${var.environment}", "/[^a-z0-9-]/", "")), 0, 32)
  alnum_name = substr(lower(replace("${var.project_name}${var.environment}", "/[^a-z0-9]/", "")), 0, 11)

  rg_name     = var.create_resource_group ? azurerm_resource_group.this[0].name : data.azurerm_resource_group.existing[0].name
  rg_location = var.create_resource_group ? azurerm_resource_group.this[0].location : data.azurerm_resource_group.existing[0].location

  effective_tracardi_password  = var.tracardi_admin_password != "" ? var.tracardi_admin_password : random_password.tracardi_admin.result
  effective_installation_token = var.installation_token != "" ? var.installation_token : random_password.installation_token.result
  effective_redis_password     = var.redis_password != "" ? var.redis_password : random_password.redis.result
  effective_mysql_password     = var.mysql_password != "" ? var.mysql_password : random_password.mysql.result

  common_tags = merge(var.tags, {
    project     = var.project_name
    environment = var.environment
    stack       = "tracardi-option-b"
  })
}

resource "azurerm_resource_group" "this" {
  count    = var.create_resource_group ? 1 : 0
  name     = var.resource_group_name
  location = var.location
  tags     = local.common_tags
}

resource "azurerm_virtual_network" "tracardi" {
  name                = "vnet-tracardi-${local.name_token}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  address_space       = [var.vnet_cidr]
  tags                = local.common_tags
}

resource "azurerm_subnet" "tracardi" {
  name                 = "snet-tracardi"
  resource_group_name  = local.rg_name
  virtual_network_name = azurerm_virtual_network.tracardi.name
  address_prefixes     = [var.tracardi_subnet_cidr]
}

resource "azurerm_subnet" "data" {
  name                 = "snet-data"
  resource_group_name  = local.rg_name
  virtual_network_name = azurerm_virtual_network.tracardi.name
  address_prefixes     = [var.data_subnet_cidr]
}

resource "azurerm_network_security_group" "tracardi" {
  name                = "nsg-tracardi-${local.name_token}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  tags                = local.common_tags
}

resource "azurerm_network_security_rule" "tracardi_ssh" {
  name                        = "allow-ssh-office"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefix       = var.admin_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.tracardi.name
}

resource "azurerm_network_security_rule" "tracardi_api_office" {
  name                        = "allow-tracardi-api-office"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8686"
  source_address_prefix       = var.office_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.tracardi.name
}

resource "azurerm_network_security_rule" "tracardi_api_containerapp" {
  name                        = "allow-tracardi-api-containerapp"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8686"
  source_address_prefix       = var.container_app_subnet_cidr
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.tracardi.name
}

resource "azurerm_network_security_rule" "tracardi_gui" {
  name                        = "allow-tracardi-gui-office"
  priority                    = 130
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8787"
  source_address_prefix       = var.office_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.tracardi.name
}

resource "azurerm_network_security_group" "data" {
  name                = "nsg-data-${local.name_token}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  tags                = local.common_tags
}

resource "azurerm_network_security_rule" "data_ssh" {
  name                        = "allow-ssh-office"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefix       = var.admin_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.data.name
}

resource "azurerm_network_security_rule" "data_es_tracardi" {
  name                        = "allow-es-from-tracardi-subnet"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "9200"
  source_address_prefix       = var.tracardi_subnet_cidr
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.data.name
}

resource "azurerm_network_security_rule" "data_es_containerapp" {
  name                        = "allow-es-from-containerapp-subnet"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "9200"
  source_address_prefix       = var.container_app_subnet_cidr
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.data.name
}

resource "azurerm_network_security_rule" "data_redis_tracardi" {
  name                        = "allow-redis-from-tracardi-subnet"
  priority                    = 130
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "6379"
  source_address_prefix       = var.tracardi_subnet_cidr
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.data.name
}

resource "azurerm_network_security_rule" "data_redis_containerapp" {
  name                        = "allow-redis-from-containerapp-subnet"
  priority                    = 140
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "6379"
  source_address_prefix       = var.container_app_subnet_cidr
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.data.name
}

resource "azurerm_subnet_network_security_group_association" "tracardi" {
  subnet_id                 = azurerm_subnet.tracardi.id
  network_security_group_id = azurerm_network_security_group.tracardi.id
}

resource "azurerm_subnet_network_security_group_association" "data" {
  subnet_id                 = azurerm_subnet.data.id
  network_security_group_id = azurerm_network_security_group.data.id
}

resource "azurerm_public_ip" "tracardi" {
  name                = "pip-tracardi-${local.name_token}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.common_tags
}

resource "azurerm_network_interface" "tracardi" {
  name                = "nic-tracardi-${local.name_token}"
  location            = local.rg_location
  resource_group_name = local.rg_name

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.tracardi.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.tracardi.id
  }

  tags = local.common_tags
}

resource "azurerm_network_interface" "data" {
  name                = "nic-data-${local.name_token}"
  location            = local.rg_location
  resource_group_name = local.rg_name

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.data.id
    private_ip_address_allocation = "Static"
    private_ip_address            = var.data_private_ip
  }

  tags = local.common_tags
}

resource "azurerm_storage_account" "tracardi" {
  name                            = substr("st${local.alnum_name}${random_string.suffix.result}", 0, 24)
  resource_group_name             = local.rg_name
  location                        = local.rg_location
  account_tier                    = var.storage_account_tier
  account_replication_type        = var.storage_replication_type
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  tags                            = local.common_tags
}

resource "azurerm_storage_container" "es_snapshots" {
  name                  = "es-snapshots"
  storage_account_name  = azurerm_storage_account.tracardi.name
  container_access_type = "private"
}

resource "azurerm_linux_virtual_machine" "data" {
  name                = "vm-data-${local.name_token}"
  resource_group_name = local.rg_name
  location            = local.rg_location
  size                = var.data_vm_size
  admin_username      = var.admin_username

  network_interface_ids = [azurerm_network_interface.data.id]

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
    name                 = "osdisk-data-${local.name_token}"
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 64
  }

  custom_data = base64encode(templatefile("${path.module}/cloud-init/data-vm.yaml.tftpl", {
    elasticsearch_image   = var.elasticsearch_image
    redis_image           = var.redis_image
    elasticsearch_heap_mb = var.elasticsearch_heap_mb
    redis_password        = local.effective_redis_password
  }))

  tags = local.common_tags
}

resource "azurerm_linux_virtual_machine" "tracardi" {
  name                = "vm-tracardi-${local.name_token}"
  resource_group_name = local.rg_name
  location            = local.rg_location
  size                = var.tracardi_vm_size
  admin_username      = var.admin_username

  network_interface_ids = [azurerm_network_interface.tracardi.id]

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
    name                 = "osdisk-tracardi-${local.name_token}"
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 64
  }

  custom_data = base64encode(templatefile("${path.module}/cloud-init/tracardi-vm.yaml.tftpl", {
    tracardi_api_image      = var.tracardi_api_image
    tracardi_gui_image      = var.tracardi_gui_image
    mysql_image             = var.mysql_image
    data_private_ip         = var.data_private_ip
    tracardi_admin_password = local.effective_tracardi_password
    installation_token      = local.effective_installation_token
    redis_password          = local.effective_redis_password
    mysql_password          = local.effective_mysql_password
  }))

  tags = local.common_tags

  depends_on = [azurerm_linux_virtual_machine.data]
}
