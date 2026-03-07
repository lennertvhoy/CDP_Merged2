#===============================================================================
# Cost Optimization Resources for CDP_Merged
#===============================================================================
# This file contains cost-related Azure resources:
# - Budget alerts
# - Cost monitoring
# - Auto-shutdown schedules (optional)
#===============================================================================

#-------------------------------------------------------------------------------
# Azure Budget with Alerts
#-------------------------------------------------------------------------------
resource "azurerm_consumption_budget_resource_group" "cdp_budget" {
  count = var.budget_alert_email != "" ? 1 : 0

  name              = "budget-${local.name_token}"
  resource_group_id = azurerm_resource_group.cdp.id
  amount            = var.monthly_budget_eur
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
    end_date   = formatdate("YYYY-MM-01'T'00:00:00Z", timeadd(timestamp(), "8760h")) # 1 year
  }

  # Alert at 50% of budget
  notification {
    enabled        = true
    threshold      = 50
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.budget_alert_email]
  }

  # Alert at 80% of budget
  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.budget_alert_email]
  }

  # Alert at 100% of budget
  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_emails = [var.budget_alert_email]
  }
}

#-------------------------------------------------------------------------------
# Data Collection Rule for Cost Optimization
# Uses the Log Analytics workspace from main.tf
#-------------------------------------------------------------------------------

# Data collection rule for sampling (reduces ingestion costs)
resource "azurerm_monitor_data_collection_rule" "cdp" {
  count = var.environment == "dev" ? 1 : 0

  name                = "dcr-${local.name_token}"
  location            = azurerm_resource_group.cdp.location
  resource_group_name = azurerm_resource_group.cdp.name

  destinations {
    log_analytics {
      workspace_resource_id = azurerm_log_analytics_workspace.cdp.id
      name                  = "law-destination"
    }
  }

  data_flow {
    streams      = ["Microsoft-InsightsMetrics"]
    destinations = ["law-destination"]
  }

  # Sample only 10% of metrics in dev
  stream_declaration {
    stream_name = "Microsoft-InsightsMetrics"
    column {
      name = "TimeGenerated"
      type = "datetime"
    }
    column {
      name = "Computer"
      type = "string"
    }
    column {
      name = "Namespace"
      type = "string"
    }
  }
}

#-------------------------------------------------------------------------------
# VM Auto-shutdown Schedule (Dev Only)
#-------------------------------------------------------------------------------
resource "azurerm_dev_test_global_vm_shutdown_schedule" "tracardi" {
  count = var.environment == "dev" && var.enable_auto_shutdown ? 1 : 0

  virtual_machine_id = azurerm_linux_virtual_machine.app.id
  location           = azurerm_resource_group.cdp.location
  enabled            = true

  daily_recurrence_time = replace(var.auto_shutdown_time, ":", "")
  timezone              = "Romance Standard Time" # UTC+1 (Brussels)

  notification_settings {
    enabled         = false
    time_in_minutes = 30
  }
}
