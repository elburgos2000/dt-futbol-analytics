#!/bin/bash
# Script de Despliegue de DT Futbol Statistics Bot en Google Cloud (Cloud Run)

PROJECT_ID=$(gcloud config get-value project)
SERVICE_NAME="dt-futbol-statistics"
REGION="us-central1"

echo "🚀 Iniciando despliegue de $SERVICE_NAME en Google Cloud Project: $PROJECT_ID"

# 1. Habilitar servicios necesarios en GCP
echo "📦 Habilitando APIs de Google Cloud..."
gcloud services enable cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com

# 2. Construir la imagen de contenedor con Cloud Build
echo "🏗️ Construyendo imagen de contenedor en Cloud Build..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME:latest .

# 3. Desplegar en Cloud Run (usando CPU siempre asignada para bot de Long Polling o Webhook)
echo "☁️ Desplegando en Google Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars TELEGRAM_BOT_TOKEN="8949954033:AAGarsw2y9qTlEQWNDMPtSev7AIRLXcA9ts",DB_PATH="/tmp/dt_futbol.db" \
    --cpu-no-throttling \
    --min-instances=1

echo "✅ ¡Despliegue finalizado con éxito en Google Cloud Run!"
