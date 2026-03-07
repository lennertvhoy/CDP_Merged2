# Virtual Network (reference existing)
data "azurerm_virtual_network" "existing" {
  name                = "vnet-cdpmerged-fast-aca"
  resource_group_name = local.resource_group_name
}

data "azurerm_subnet" "existing" {
  name                 = "snet-containerapps-infra"
  virtual_network_name = data.azurerm_virtual_network.existing.name
  resource_group_name  = local.resource_group_name
}

# Public IP for Tracardi VM
resource "azurerm_public_ip" "tracardi" {
  name                = "pip-${local.vm_name}"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = local.location
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

# Network Security Group for Tracardi
resource "azurerm_network_security_group" "tracardi" {
  name                = "nsg-${local.vm_name}"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = local.location
  tags                = local.tags

  # SSH - Office IP only
  security_rule {
    name                       = "Allow-SSH-Office"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = local.office_ip
    destination_address_prefix = "*"
  }

  # SSH - Current client IP
  security_rule {
    name                       = "Allow-SSH-Client"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "${chomp(data.http.client_ip.response_body)}/32"
    destination_address_prefix = "*"
  }

  # Tracardi API - Office IP only
  security_rule {
    name                       = "Allow-Tracardi-API"
    priority                   = 200
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8686"
    source_address_prefix      = local.office_ip
    destination_address_prefix = "*"
  }

  # Tracardi GUI - Office IP only
  security_rule {
    name                       = "Allow-Tracardi-GUI"
    priority                   = 210
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8787"
    source_address_prefix      = local.office_ip
    destination_address_prefix = "*"
  }

  # Webhook endpoints - Allow any IP (webhooks from external services)
  security_rule {
    name                       = "Allow-Webhooks"
    priority                   = 300
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["80", "443", "8686"]
    source_address_prefix      = "*"
    destination_address_prefix = "*"
    description                = "Allow webhook calls from Teamleader, Brevo, etc"
  }

  # HTTP - Any IP (redirect to HTTPS/Tracardi)
  security_rule {
    name                       = "Allow-HTTP"
    priority                   = 400
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # HTTPS - Any IP
  security_rule {
    name                       = "Allow-HTTPS"
    priority                   = 410
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Deny all other inbound
  security_rule {
    name                       = "Deny-All-Inbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# Network Interface
resource "azurerm_network_interface" "tracardi" {
  name                = "nic-${local.vm_name}"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = local.location
  tags                = local.tags

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = data.azurerm_subnet.existing.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.tracardi.id
  }
}

# NSG Association
resource "azurerm_network_interface_security_group_association" "tracardi" {
  network_interface_id      = azurerm_network_interface.tracardi.id
  network_security_group_id = azurerm_network_security_group.tracardi.id
}
