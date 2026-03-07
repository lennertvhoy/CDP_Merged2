terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

locals {
  resource_group_name = "rg-cdpmerged-fast"
  location           = "westeurope"
  vm_name            = "vm-tracardi-eventhub"
  admin_username     = "azureuser"
  office_ip          = "78.21.222.70/32"
  tags = {
    environment = "prod"
    component   = "eventhub"
    cost_center = "cdp"
    temporary   = "false"
  }
}

# Reference existing resource group
data "azurerm_resource_group" "rg" {
  name = local.resource_group_name
}

# Get current client IP for SSH access
data "http" "client_ip" {
  url = "https://api.ipify.org"
}
