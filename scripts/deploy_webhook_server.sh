#!/bin/bash
# Deploy webhook server to Azure Container Instance

RESOURCE_GROUP="rg-cdpmerged-fast"
CONTAINER_NAME="cdp-webhook-server"
IMAGE="python:3.11-slim"

# Create container
echo "Creating webhook server container..."

az container create \
  --resource-group $RESOURCE_GROUP \
  --name $CONTAINER_NAME \
  --image $IMAGE \
  --cpu 1 \
  --memory 1 \
  --ports 8080 \
  --ip-address public \
  --dns-name-label cdp-webhooks \
  --command-line "/bin/bash -c 'pip install flask azure-eventhub python-dotenv && python /app/webhook_server.py'" \
  --file ~/.env.database \
  --volume ./scripts/webhook_server.py:/app/webhook_server.py

echo "Webhook server deployed!"
echo "URL: http://cdp-webhooks.westeurope.azurecontainer.io:8080"
