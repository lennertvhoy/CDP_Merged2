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

resource "random_password" "mysql" {
  length           = 20
  special          = true
  override_special = "!@%^*-_"
}

locals {
  name_token  = substr(lower(replace("${var.project_name}-${var.environment}", "/[^a-z0-9-]/", "")), 0, 32)
  alnum_name  = substr(lower(replace("${var.project_name}${var.environment}", "/[^a-z0-9]/", "")), 0, 11)
  
  effective_tracardi_password  = var.tracardi_admin_password != "" ? var.tracardi_admin_password : random_password.tracardi_admin.result
  effective_installation_token = var.installation_token != "" ? var.installation_token : random_password.installation_token.result
  effective_mysql_password     = var.mysql_password != "" ? var.mysql_password : random_password.mysql.result

  common_tags = merge(var.tags, {
    project     = var.project_name
    environment = var.environment
    stack       = "tracardi-minimal"
  })
}

# Resource Group (data source if not creating)
data "azurerm_resource_group" "existing" {
  count = var.create_resource_group ? 0 : 1
  name  = var.resource_group_name
}

resource "azurerm_resource_group" "this" {
  count    = var.create_resource_group ? 1 : 0
  name     = var.resource_group_name
  location = var.location
  tags     = local.common_tags
}

locals {
  rg_name     = var.create_resource_group ? azurerm_resource_group.this[0].name : data.azurerm_resource_group.existing[0].name
  rg_location = var.create_resource_group ? azurerm_resource_group.this[0].location : data.azurerm_resource_group.existing[0].location
}

# Virtual Network
resource "azurerm_virtual_network" "tracardi" {
  name                = "vnet-tracardi-${local.name_token}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  address_space       = [var.vnet_cidr]
  tags                = local.common_tags
}

# Subnet
resource "azurerm_subnet" "tracardi" {
  name                 = "snet-tracardi"
  resource_group_name  = local.rg_name
  virtual_network_name = azurerm_virtual_network.tracardi.name
  address_prefixes     = [var.subnet_cidr]
}

# Network Security Group
resource "azurerm_network_security_group" "tracardi" {
  name                = "nsg-tracardi-${local.name_token}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  tags                = local.common_tags
}

# NSG Rule: Allow SSH from office
resource "azurerm_network_security_rule" "ssh" {
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

# NSG Rule: Allow HTTP webhooks (from anywhere)
resource "azurerm_network_security_rule" "http" {
  name                        = "allow-http-webhooks"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "80"
  source_address_prefix       = "*"
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.tracardi.name
}

# NSG Rule: Allow HTTPS webhooks (from anywhere)
resource "azurerm_network_security_rule" "https" {
  name                        = "allow-https-webhooks"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "*"
  destination_address_prefix  = "*"
  resource_group_name         = local.rg_name
  network_security_group_name = azurerm_network_security_group.tracardi.name
}

# NSG Rule: Allow Tracardi API (port 8686) - office only for admin
resource "azurerm_network_security_rule" "tracardi_api" {
  name                        = "allow-tracardi-api"
  priority                    = 130
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

# NSG Rule: Allow Tracardi GUI (port 8787) - office only for admin
resource "azurerm_network_security_rule" "tracardi_gui" {
  name                        = "allow-tracardi-gui"
  priority                    = 140
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

# NSG Association
resource "azurerm_subnet_network_security_group_association" "tracardi" {
  subnet_id                 = azurerm_subnet.tracardi.id
  network_security_group_id = azurerm_network_security_group.tracardi.id
}

# Public IP
resource "azurerm_public_ip" "tracardi" {
  name                = "pip-tracardi-${local.name_token}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.common_tags
}

# Network Interface
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

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "tracardi" {
  name                = "law-tracardi-${local.name_token}-${random_string.suffix.result}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.common_tags
}

# Linux VM - Tracardi EventHub (Minimal)
resource "azurerm_linux_virtual_machine" "tracardi" {
  name                = "vm-tracardi-eventhub"
  resource_group_name = local.rg_name
  location            = local.rg_location
  size                = var.vm_size
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
    disk_size_gb         = var.os_disk_size_gb
  }

  custom_data = base64encode(templatefile("${path.module}/cloud-init/tracardi-minimal.yaml.tftpl", {
    tracardi_api_image      = var.tracardi_api_image
    tracardi_gui_image      = var.tracardi_gui_image
    mysql_image             = var.mysql_image
    tracardi_admin_password = local.effective_tracardi_password
    installation_token      = local.effective_installation_token
    mysql_password          = local.effective_mysql_password
  }))

  tags = merge(local.common_tags, {
    environment = "prod"
    component   = "eventhub"
    cost_center = "cdp"
    temporary   = "false"
  })
}

# Azure Monitor Diagnostic Setting for VM
resource "azurerm_monitor_diagnostic_setting" "vm" {
  name                       = "diag-vm-tracardi"
  target_resource_id         = azurerm_linux_virtual_machine.tracardi.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.tracardi.id

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
