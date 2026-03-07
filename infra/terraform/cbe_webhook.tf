# CBE Webhook Listener - Azure Container App
# Deploys a FastAPI service to receive CBE company change events

locals {
  cbe_webhook_name = "ca-cbe-webhook-${var.environment}"
}

# Container App Environment for CBE Webhook
resource "azurerm_container_app_environment" "cbe_webhook" {
  name                = "cae-cbe-webhook-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name

  tags = {
    environment = var.environment
    service     = "cbe-webhook"
    managed_by  = "terraform"
  }
}

# CBE Webhook Container App
resource "azurerm_container_app" "cbe_webhook" {
  name                         = local.cbe_webhook_name
  container_app_environment_id = azurerm_container_app_environment.cbe_webhook.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  template {
    container {
      name   = "cbe-webhook"
      image  = "${var.container_registry}/cbe-webhook:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
    }

    min_replicas = 1
    max_replicas = 3
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  tags = {
    environment = var.environment
    service     = "cbe-webhook"
    version     = var.image_tag
  }
}

# Output the webhook endpoint URL
output "cbe_webhook_endpoint" {
  description = "URL for CBE webhook endpoint"
  value       = "https://${azurerm_container_app.cbe_webhook.ingress[0].fqdn}/webhook/cbe"
}

output "cbe_webhook_health_url" {
  description = "Health check URL"
  value       = "https://${azurerm_container_app.cbe_webhook.ingress[0].fqdn}/health"
}

# Variables unique to CBE webhook (others are in variables.tf)
variable "container_registry" {
  description = "Container registry URL"
  type        = string
  default     = "ghcr.io/lennertvhoy"
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
}

