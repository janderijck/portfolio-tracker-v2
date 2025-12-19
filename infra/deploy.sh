#!/bin/bash

# Portfolio Tracker - Azure Deployment Script
# Usage: ./deploy.sh [--resource-group <name>] [--location <location>]

set -e

# Default values
RESOURCE_GROUP="rg-portfolio-tracker"
LOCATION="westeurope"
BASE_NAME="portfoliotracker"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --resource-group|-g)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        --location|-l)
            LOCATION="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: ./deploy.sh [--resource-group <name>] [--location <location>]"
            echo ""
            echo "Options:"
            echo "  -g, --resource-group  Azure resource group name (default: rg-portfolio-tracker)"
            echo "  -l, --location        Azure region (default: westeurope)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=============================================="
echo "Portfolio Tracker - Azure Deployment"
echo "=============================================="
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "=============================================="

# Check if logged in to Azure
echo ""
echo "[1/7] Checking Azure CLI login..."
if ! az account show > /dev/null 2>&1; then
    echo "Not logged in to Azure. Running 'az login'..."
    az login
fi

SUBSCRIPTION=$(az account show --query name -o tsv)
echo "Using subscription: $SUBSCRIPTION"

# Create resource group
echo ""
echo "[2/7] Creating resource group..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none

echo "Resource group '$RESOURCE_GROUP' created."

# Deploy infrastructure
echo ""
echo "[3/7] Deploying Azure infrastructure (this may take a few minutes)..."
DEPLOYMENT_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file main.bicep \
    --parameters location="$LOCATION" baseName="$BASE_NAME" \
    --query "properties.outputs" \
    --output json)

# Extract outputs
ACR_NAME=$(echo $DEPLOYMENT_OUTPUT | jq -r '.acrName.value')
ACR_LOGIN_SERVER=$(echo $DEPLOYMENT_OUTPUT | jq -r '.acrLoginServer.value')
FRONTEND_URL=$(echo $DEPLOYMENT_OUTPUT | jq -r '.frontendUrl.value')
BACKEND_URL=$(echo $DEPLOYMENT_OUTPUT | jq -r '.backendUrl.value')

echo "Infrastructure deployed successfully!"
echo "  ACR: $ACR_LOGIN_SERVER"

# Login to ACR
echo ""
echo "[4/7] Logging in to Azure Container Registry..."
az acr login --name "$ACR_NAME"

# Build and push backend
echo ""
echo "[5/7] Building and pushing backend image..."
cd ../backend
docker build -t "$ACR_LOGIN_SERVER/portfolio-backend:latest" .
docker push "$ACR_LOGIN_SERVER/portfolio-backend:latest"
cd ../infra

# Build and push frontend
echo ""
echo "[6/7] Building and pushing frontend image..."
cd ../frontend
docker build -t "$ACR_LOGIN_SERVER/portfolio-frontend:latest" .
docker push "$ACR_LOGIN_SERVER/portfolio-frontend:latest"
cd ../infra

# Update container apps with new images
echo ""
echo "[7/7] Updating container apps..."
az containerapp update \
    --name "ca-${BASE_NAME}-backend" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/portfolio-backend:latest" \
    --output none

az containerapp update \
    --name "ca-${BASE_NAME}-frontend" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/portfolio-frontend:latest" \
    --output none

echo ""
echo "=============================================="
echo "Deployment Complete!"
echo "=============================================="
echo ""
echo "Frontend URL: $FRONTEND_URL"
echo "Backend URL:  $BACKEND_URL"
echo "API Docs:     $BACKEND_URL/docs"
echo ""
echo "Note: It may take a few minutes for the containers to start."
echo "=============================================="
