#===============================================================================
# CDP_Merged Infrastructure - Cost Optimization Module
#===============================================================================
#
# This module provides conditional resource sizing based on environment.
# Usage: Set the 'environment' variable to 'dev' or 'prod' to automatically
#        apply appropriate cost optimizations.
#
# Example:
#   module "cost_optimized_infra" {
#     source      = "./modules/cost-optimized"
#     environment = "dev"  # Automatically applies dev optimizations
#   }
#===============================================================================

# Local values for environment-based sizing
locals {
  # Environment detection
  is_dev  = var.environment == "dev"
  is_prod = var.environment == "prod"

  # Container App sizing
  container_app_config = {
    dev = {
      cpu            = 0.25
      memory         = "0.5Gi"
      min_replicas   = 0
      max_replicas   = 5
    }
    prod = {
      cpu            = 0.5
      memory         = "1Gi"
      min_replicas   = 1
      max_replicas   = 10
    }
  }

  # VM sizing
  vm_config = {
    dev = {
      tracerdati_size = "Standard_B2s"  # Keep for data integrity
      data_size       = "Standard_B1ls" # Reduced for dev
    }
    prod = {
      tracerdati_size = "Standard_B2s"
      data_size       = "Standard_B1ms"
    }
  }

  # Azure Search sizing
  search_config = {
    dev = {
      sku              = "free"
      replica_count    = 1
      partition_count  = 1
    }
    prod = {
      sku              = "basic"
      replica_count    = 1
      partition_count  = 1
    }
  }

  # Selected configuration based on environment
  selected_container_app = local.container_app_config[var.environment]
  selected_vm            = local.vm_config[var.environment]
  selected_search        = local.search_config[var.environment]
}

# Outputs for use in main.tf
output "container_app_cpu" {
  description = "Container App CPU allocation"
  value       = local.selected_container_app.cpu
}

output "container_app_memory" {
  description = "Container App memory allocation"
  value       = local.selected_container_app.memory
}

output "container_app_min_replicas" {
  description = "Container App minimum replicas"
  value       = local.selected_container_app.min_replicas
}

output "container_app_max_replicas" {
  description = "Container App maximum replicas"
  value       = local.selected_container_app.max_replicas
}

output "tracerdati_vm_size" {
  description = "Tracardi VM size"
  value       = local.selected_vm.tracerdati_size
}

output "data_vm_size" {
  description = "Data VM size"
  value       = local.selected_vm.data_size
}

output "search_sku" {
  description = "Azure AI Search SKU"
  value       = local.selected_search.sku
}

output "search_replica_count" {
  description = "Azure AI Search replica count"
  value       = local.selected_search.replica_count
}

output "search_partition_count" {
  description = "Azure AI Search partition count"
  value       = local.selected_search.partition_count
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost in EUR"
  value       = local.is_dev ? "€80-110" : "€173-228"
}
