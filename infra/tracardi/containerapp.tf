# --------------------------------------------------------------------------
# Log Analytics Workspace + Container App Environment + Container App
# --------------------------------------------------------------------------
# Import existing resources:
#   terraform import azurerm_log_analytics_workspace.this <resource-id>
#   terraform import azurerm_container_app_environment.this <resource-id>
#   terraform import azurerm_container_app.chatbot <resource-id>
# --------------------------------------------------------------------------

resource "azurerm_log_analytics_workspace" "this" {
  name                = "law-tracardi-${local.name_token}-${random_string.suffix.result}"
  location            = local.rg_location
  resource_group_name = local.rg_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.common_tags
}

resource "azurerm_container_app_environment" "this" {
  name                       = "ca-${local.name_token}-env"
  location                   = local.rg_location
  resource_group_name        = local.rg_name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  tags                       = local.common_tags
}

resource "azurerm_container_app" "chatbot" {
  name                         = "ca-${local.name_token}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = local.rg_name
  revision_mode                = "Single"
  tags                         = local.common_tags

  template {
    min_replicas = var.container_app_min_replicas
    max_replicas = var.container_app_max_replicas

    container {
      name   = "cdp-chatbot"
      image  = var.container_app_image
      cpu    = 0.5
      memory = "1Gi"

      # Non-secret environment variables
      env {
        name  = "LLM_PROVIDER"
        value = "azure_openai"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      env {
        name  = "DEBUG"
        value = "false"
      }
      env {
        name  = "CHAINLIT_PORT"
        value = "8000"
      }
      env {
        name  = "TRACARDI_API_URL"
        value = "http://${azurerm_public_ip.tracardi.ip_address}:8686"
      }
      env {
        name  = "TRACARDI_SOURCE_ID"
        value = "kbo-source"
      }
      env {
        name  = "TRACARDI_USERNAME"
        value = "admin@admin.com"
      }
      env {
        name        = "TRACARDI_PASSWORD"
        secret_name = "tracardi-password"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = "https://${azurerm_cognitive_account.openai.custom_subdomain_name}.openai.azure.com/"
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "azure-openai-key"
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_NAME"
        value = var.openai_deployment_name
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT"
        value = var.openai_deployment_name
      }
      env {
        name  = "AZURE_AUTH_USE_DEFAULT_CREDENTIAL"
        value = "false"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name  = "DEPLOY_TIMESTAMP"
        value = tostring(var.deploy_timestamp)
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # Secrets are managed externally (az containerapp secret set)
  # to avoid storing sensitive values in Terraform state.
  # Only declare the secret names here; values are set via CLI.
  secret {
    name  = "tracardi-password"
    value = var.tracardi_admin_password != "" ? var.tracardi_admin_password : "placeholder"
  }
  secret {
    name  = "azure-openai-key"
    value = var.azure_openai_api_key != "" ? var.azure_openai_api_key : "placeholder"
  }
  secret {
    name  = "database-url"
    value = var.database_url != "" ? var.database_url : "placeholder"
  }

  lifecycle {
    # Image tag and secrets are managed by CI/CD pipeline
    ignore_changes = [
      template[0].container[0].image,
      secret,
      template[0].container[0].env,
    ]
  }
}
