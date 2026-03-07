# --------------------------------------------------------------------------
# Azure OpenAI (Cognitive Services)
# --------------------------------------------------------------------------
# Import: terraform import azurerm_cognitive_account.openai <resource-id>
# --------------------------------------------------------------------------

resource "azurerm_cognitive_account" "openai" {
  name                  = "aoai-${local.name_token}"
  location              = local.rg_location
  resource_group_name   = local.rg_name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "aoai-${local.name_token}"

  public_network_access_enabled = true

  tags = local.common_tags

  lifecycle {
    # Prevent accidental deletion of the OpenAI resource
    prevent_destroy = true
  }
}
