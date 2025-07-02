#!/bin/bash
set -e

# Configuration
JOB_TAG="v6-11"
JOB_NAME="x-daily-hire-screenshot-job-${JOB_TAG}"
IMAGE_NAME="europe-west2-docker.pkg.dev/intelligent-recruitment-engine/recruitment-engine-repo/${JOB_NAME}:${JOB_TAG}"
REGION="europe-west2"
MEMORY="8Gi"
CPU="2"
TASK_TIMEOUT="1800s"
DB_CONNECTION_INSTANCE="intelligent-recruitment-engine:europe-west2:recruitment-db-main"

echo "🚀 Starting deployment of ${JOB_NAME}..."

# Build and push image
echo "🔨 Building Docker image..."
docker build --no-cache --memory 4g --shm-size 2g -t "${IMAGE_NAME}" . || {
  echo "❌ Docker build failed"
  exit 1
}

echo "📤 Pushing image to Artifact Registry..."
docker push "${IMAGE_NAME}" || {
  echo "❌ Docker push failed"
  exit 1
}

# Deploy Cloud Run Job
echo "☁️ Deploying Cloud Run Job..."
gcloud run jobs deploy "${JOB_NAME}" \
  --region="${REGION}" \
  --image="${IMAGE_NAME}" \
  --memory="${MEMORY}" \
  --cpu="${CPU}" \
  --task-timeout="${TASK_TIMEOUT}" \
  --set-env-vars="DB_CONNECTION_NAME=${DB_CONNECTION_INSTANCE}" \
  --set-env-vars="HIRE_USERNAME=crootonmaster@applygateway.com" \
  --set-env-vars="DEBUG_SCREENSHOT_BUCKET=recruitment-engine-cvs-sp-260625" \
  --set-env-vars="SE_SHM_SIZE=2g" \
  --set-secrets="HIRE_PASSWORD=hire-password:latest" \
  --set-secrets="DB_USER=db-user:latest" \
  --set-secrets="DB_PASSWORD=db-password:latest" \
  --set-secrets="DB_NAME=db-name:latest" \
  --set-cloudsql-instances="${DB_CONNECTION_INSTANCE}" \
  --service-account="screenshot-runner@intelligent-recruitment-engine.iam.gserviceaccount.com" || {
  echo "❌ Job deployment failed"
  exit 1
}

echo "✅ Successfully deployed ${JOB_NAME}"
echo "👉 Execute manually: gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
echo "📋 View logs: gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}' --limit=50"
