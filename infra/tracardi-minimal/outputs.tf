output "vm_public_ip" {
  description = "Public IP address of the Tracardi EventHub VM"
  value       = azurerm_public_ip.tracardi.ip_address
}

output "vm_private_ip" {
  description = "Private IP address of the Tracardi EventHub VM"
  value       = azurerm_network_interface.tracardi.private_ip_address
}

output "vm_name" {
  description = "Name of the Tracardi VM"
  value       = azurerm_linux_virtual_machine.tracardi.name
}

output "resource_group_name" {
  description = "Resource group name"
  value       = local.rg_name
}

output "tracardi_api_url" {
  description = "URL for Tracardi API"
  value       = "http://${azurerm_public_ip.tracardi.ip_address}:8686"
}

output "tracardi_gui_url" {
  description = "URL for Tracardi GUI"
  value       = "http://${azurerm_public_ip.tracardi.ip_address}:8787"
}

output "health_check_url" {
  description = "Health check endpoint URL"
  value       = "http://${azurerm_public_ip.tracardi.ip_address}:8686/health"
}

output "tracardi_admin_password" {
  description = "Tracardi admin password"
  value       = local.effective_tracardi_password
  sensitive   = true
}

output "installation_token" {
  description = "Tracardi installation token"
  value       = local.effective_installation_token
  sensitive   = true
}

output "mysql_password" {
  description = "MySQL root password"
  value       = local.effective_mysql_password
  sensitive   = true
}

output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID"
  value       = azurerm_log_analytics_workspace.tracardi.id
}

output "ssh_command" {
  description = "SSH command to connect to the VM"
  value       = "ssh ${var.admin_username}@${azurerm_public_ip.tracardi.ip_address}"
}
