# Virtual Machine - Standard_B1ms (€13/mo)
resource "azurerm_linux_virtual_machine" "tracardi" {
  name                = local.vm_name
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = local.location
  size                = "Standard_B1ms"
  admin_username      = local.admin_username
  tags                = local.tags

  network_interface_ids = [
    azurerm_network_interface.tracardi.id
  ]

  admin_ssh_key {
    username   = local.admin_username
    public_key = file("~/.ssh/id_rsa.pub")
  }

  os_disk {
    name                 = "osdisk-${local.vm_name}"
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = 32
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  # Enable VM extension for Azure Monitor
  identity {
    type = "SystemAssigned"
  }

  # User data for initial setup
  custom_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tmpl", {
    admin_username = local.admin_username
  }))

  # Boot diagnostics
  boot_diagnostics {
    storage_account_uri = null  # Use managed storage
  }
}

# Data source for existing Log Analytics workspace
data "azurerm_log_analytics_workspace" "existing" {
  name                = "workspace-rgcdpmergedfastF2eP"
  resource_group_name = local.resource_group_name
}

# Azure Monitor VM extension
resource "azurerm_virtual_machine_extension" "monitor" {
  name                       = "AzureMonitorLinuxAgent"
  virtual_machine_id         = azurerm_linux_virtual_machine.tracardi.id
  publisher                  = "Microsoft.Azure.Monitor"
  type                       = "AzureMonitorLinuxAgent"
  type_handler_version       = "1.0"
  auto_upgrade_minor_version = true
}

# Output VM IP
output "vm_public_ip" {
  value       = azurerm_public_ip.tracardi.ip_address
  description = "Public IP of the Tracardi event hub VM"
}

output "vm_private_ip" {
  value       = azurerm_network_interface.tracardi.private_ip_address
  description = "Private IP of the Tracardi event hub VM"
}

output "vm_name" {
  value       = azurerm_linux_virtual_machine.tracardi.name
  description = "Name of the Tracardi VM"
}

output "ssh_command" {
  value       = "ssh ${local.admin_username}@${azurerm_public_ip.tracardi.ip_address}"
  description = "SSH command to connect to the VM"
}

output "tracardi_api_url" {
  value       = "http://${azurerm_public_ip.tracardi.ip_address}:8686"
  description = "Tracardi API endpoint"
}

output "tracardi_gui_url" {
  value       = "http://${azurerm_public_ip.tracardi.ip_address}:8787"
  description = "Tracardi GUI endpoint"
}
