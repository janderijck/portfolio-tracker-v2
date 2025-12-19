# Deployment Guide - Azure Container Apps

Deze handleiding beschrijft hoe je de Portfolio Tracker applicatie deployt naar Azure Container Apps.

## Architectuur Overzicht

```
                        Internet
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                 Azure Container Apps Environment               │
│                                                                 │
│   ┌─────────────────────┐       ┌─────────────────────┐       │
│   │      Frontend       │       │      Backend        │       │
│   │   (Nginx + React)   │──────▶│     (FastAPI)       │       │
│   │   External Ingress  │ /api  │   Internal Ingress  │       │
│   └─────────────────────┘       └──────────┬──────────┘       │
│                                             │                  │
│                                   ┌─────────▼─────────┐       │
│                                   │   Azure Files     │       │
│                                   │  (portfolio.db)   │       │
│                                   └───────────────────┘       │
└───────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Vereiste Tools

```bash
# Azure CLI (versie 2.50+)
az --version

# Docker
docker --version

# Git
git --version
```

### Azure Account Setup

1. **Azure Subscription**: Zorg dat je een actieve Azure subscription hebt
2. **Azure CLI Login**:
   ```bash
   az login
   az account set --subscription "<subscription-name-or-id>"
   ```

## Deployment Opties

### Optie 1: Automatisch via GitHub Actions (Aanbevolen)

Bij elke push naar de `main` branch wordt automatisch gedeployed.

#### Eerste Keer Setup

1. **Fork/Clone de repository naar GitHub**

2. **Maak Azure Service Principal aan**:
   ```bash
   az ad sp create-for-rbac \
     --name "sp-portfolio-tracker" \
     --role contributor \
     --scopes /subscriptions/<subscription-id> \
     --sdk-auth
   ```
   
   Kopieer de JSON output.

3. **Configureer GitHub Secrets**:
   
   Ga naar je GitHub repo → Settings → Secrets and variables → Actions
   
   Voeg toe:
   | Secret Name | Value |
   |-------------|-------|
   | `AZURE_CREDENTIALS` | De volledige JSON van stap 2 |
   | `AZURE_SUBSCRIPTION_ID` | Je Azure subscription ID |

4. **Trigger eerste deployment**:
   ```bash
   git push origin main
   ```

### Optie 2: Handmatige Deployment via Script

```bash
cd infra
chmod +x deploy.sh
./deploy.sh
```

## Handmatige Stap-voor-Stap Deployment

### Stap 1: Resource Group Aanmaken

```bash
# Variables
RESOURCE_GROUP="rg-portfolio-tracker"
LOCATION="westeurope"

# Create resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION
```

### Stap 2: Azure Container Registry

```bash
ACR_NAME="acrportfoliotracker"

# Create container registry
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true

# Get credentials
az acr credential show --name $ACR_NAME
```

### Stap 3: Build en Push Docker Images

```bash
# Login to ACR
az acr login --name $ACR_NAME

# Build and push backend
docker build -t $ACR_NAME.azurecr.io/portfolio-backend:latest ./backend
docker push $ACR_NAME.azurecr.io/portfolio-backend:latest

# Build and push frontend
docker build -t $ACR_NAME.azurecr.io/portfolio-frontend:latest ./frontend
docker push $ACR_NAME.azurecr.io/portfolio-frontend:latest
```

### Stap 4: Storage Account voor Database

```bash
STORAGE_ACCOUNT="stportfoliotracker"

# Create storage account
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS

# Create file share
az storage share create \
  --name portfolio-data \
  --account-name $STORAGE_ACCOUNT

# Get storage key
STORAGE_KEY=$(az storage account keys list \
  --resource-group $RESOURCE_GROUP \
  --account-name $STORAGE_ACCOUNT \
  --query '[0].value' -o tsv)
```

### Stap 5: Container Apps Environment

```bash
ENV_NAME="cae-portfolio-tracker"

# Create Container Apps environment
az containerapp env create \
  --name $ENV_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Add storage to environment
az containerapp env storage set \
  --name $ENV_NAME \
  --resource-group $RESOURCE_GROUP \
  --storage-name portfoliodata \
  --azure-file-account-name $STORAGE_ACCOUNT \
  --azure-file-account-key $STORAGE_KEY \
  --azure-file-share-name portfolio-data \
  --access-mode ReadWrite
```

### Stap 6: Deploy Backend Container App

```bash
# Get ACR credentials
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

# Deploy backend
az containerapp create \
  --name ca-portfolio-backend \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image $ACR_NAME.azurecr.io/portfolio-backend:latest \
  --registry-server $ACR_NAME.azurecr.io \
  --registry-username $ACR_NAME \
  --registry-password $ACR_PASSWORD \
  --target-port 8000 \
  --ingress internal \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars "DATABASE_PATH=/data/portfolio.db"

# Mount storage volume
az containerapp update \
  --name ca-portfolio-backend \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars "DATABASE_PATH=/data/portfolio.db" \
  --replace-env-vars
```

### Stap 7: Deploy Frontend Container App

```bash
# Get backend FQDN
BACKEND_FQDN=$(az containerapp show \
  --name ca-portfolio-backend \
  --resource-group $RESOURCE_GROUP \
  --query "properties.configuration.ingress.fqdn" -o tsv)

# Deploy frontend
az containerapp create \
  --name ca-portfolio-frontend \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image $ACR_NAME.azurecr.io/portfolio-frontend:latest \
  --registry-server $ACR_NAME.azurecr.io \
  --registry-username $ACR_NAME \
  --registry-password $ACR_PASSWORD \
  --target-port 80 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --env-vars "BACKEND_URL=https://$BACKEND_FQDN"
```

### Stap 8: Verkrijg de URL

```bash
# Get frontend URL
az containerapp show \
  --name ca-portfolio-frontend \
  --resource-group $RESOURCE_GROUP \
  --query "properties.configuration.ingress.fqdn" -o tsv
```

Je applicatie is nu bereikbaar op `https://ca-portfolio-frontend.<random>.westeurope.azurecontainerapps.io`

## Kosten Overzicht

| Resource | Geschatte Kosten/Maand |
|----------|------------------------|
| Container Apps (2 apps, minimal) | ~€10-20 |
| Container Registry (Basic) | ~€5 |
| Storage Account (minimal) | ~€1-2 |
| **Totaal** | **~€15-30** |

*Kosten zijn afhankelijk van gebruik. Container Apps gebruikt consumption-based pricing.*

## Updates Deployen

### Via GitHub Actions

Push naar main branch triggered automatisch een nieuwe deployment.

### Handmatig

```bash
# Build nieuwe images
docker build -t $ACR_NAME.azurecr.io/portfolio-backend:latest ./backend
docker build -t $ACR_NAME.azurecr.io/portfolio-frontend:latest ./frontend

# Push
docker push $ACR_NAME.azurecr.io/portfolio-backend:latest
docker push $ACR_NAME.azurecr.io/portfolio-frontend:latest

# Update containers (ze pullen automatisch nieuwe images)
az containerapp update --name ca-portfolio-backend --resource-group $RESOURCE_GROUP
az containerapp update --name ca-portfolio-frontend --resource-group $RESOURCE_GROUP
```

## Monitoring & Logging

### Logs Bekijken

```bash
# Backend logs
az containerapp logs show \
  --name ca-portfolio-backend \
  --resource-group $RESOURCE_GROUP \
  --follow

# Frontend logs
az containerapp logs show \
  --name ca-portfolio-frontend \
  --resource-group $RESOURCE_GROUP \
  --follow
```

### Metrics

Bekijk metrics in Azure Portal:
1. Ga naar je Container App
2. Klik op "Metrics" in het menu
3. Selecteer metrics zoals CPU, Memory, Requests

## Troubleshooting

### Container Start Niet

```bash
# Check logs
az containerapp logs show --name ca-portfolio-backend --resource-group $RESOURCE_GROUP

# Check revision status
az containerapp revision list --name ca-portfolio-backend --resource-group $RESOURCE_GROUP
```

### Database Issues

```bash
# Check if storage is mounted
az containerapp show \
  --name ca-portfolio-backend \
  --resource-group $RESOURCE_GROUP \
  --query "properties.template.volumes"
```

### CORS Errors

Controleer of de frontend URL is toegevoegd aan de CORS settings in `backend/app/main.py`.

## Cleanup

Om alle resources te verwijderen:

```bash
az group delete --name rg-portfolio-tracker --yes --no-wait
```

## Custom Domain (Optioneel)

```bash
# Add custom domain
az containerapp hostname add \
  --name ca-portfolio-frontend \
  --resource-group $RESOURCE_GROUP \
  --hostname portfolio.jouwdomein.nl

# Bind certificate (managed)
az containerapp hostname bind \
  --name ca-portfolio-frontend \
  --resource-group $RESOURCE_GROUP \
  --hostname portfolio.jouwdomein.nl \
  --environment $ENV_NAME \
  --validation-method CNAME
```

## Meer Informatie

- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Azure Container Registry Documentation](https://learn.microsoft.com/en-us/azure/container-registry/)
- [GitHub Actions for Azure](https://github.com/Azure/actions)
