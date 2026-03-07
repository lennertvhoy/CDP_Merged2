// ACA VNet deployment with WebSocket support for CDP_Merged
// Deploy: az deployment group create -g rg-cdpmerged-prod -f aca_vnet_websocket.bicep

param location string = resourceGroup().location
param appName string = 'ca-cdpmerged-fast-vnet'
param containerImage string = 'ghcr.io/lennertvhoy/cdp_merged:latest'
param acrServer string = 'ghcr.io'

// Environment variables from your current deployment
param tracardiApiUrl string = 'http://52.148.232.140:8686'
param tracardiUsername string = 'admin@cdpmerged.local'
@secure()
param tracardiPassword string

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: resourceId('Microsoft.App/managedEnvironments', 'env-cdpmerged-vnet')
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'  // REQUIRED for WebSocket support
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      secrets: [
        {
          name: 'tracardi-password'
          value: tracardiPassword
        }
      ]
      registries: [
        {
          server: acrServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          env: [
            {
              name: 'TRACARDI_API_URL'
              value: tracardiApiUrl
            }
            {
              name: 'TRACARDI_USERNAME'
              value: tracardiUsername
            }
            {
              name: 'TRACARDI_PASSWORD'
              secretRef: 'tracardi-password'
            }
            {
              name: 'CHAINLIT_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'CHAINLIT_PORT'
              value: '8000'
            }
          ]
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/project/settings'
                port: 8000
              }
              initialDelaySeconds: 30
              periodSeconds: 10
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/project/settings'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
