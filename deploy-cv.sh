#!/bin/bash

set -e  # Exit on error

# Define common variables
JOB_TAG="v10-01" # Update your JOB_TAG if you retry the deploy
JOB_NAME="daily-hire-screenshot-job-${JOB_TAG}"
IMAGE_NAME="europe-west2-docker.pkg.dev/intelligent-recruitment-engine/recruitment-engine-repo/${JOB_NAME}:${JOB_TAG}"
REGION="europe-west2"
MEMORY="2Gi"
CPU="1"
TASK_TIMEOUT="1800"
DB_CONNECTION_INSTANCE="intelligent-recruitment-engine:europe-west2:recruitment-db-main"

# Step 1: Prepare workspace
echo "Step 1: Preparing workspace..."
cd ~/ || exit 1
rm -rf loop-cvs
git clone https://github.com/crootonSMP/loop-pull-hi-cvs.git loop-cvs || exit 1
cd loop-cvs || exit 1

echo "Current directory contents:"
ls -l
echo "Dockerfile snippet:"
head -n 20 Dockerfile
echo "requirements.txt content:"
cat requirements.txt

# Step 2: Build and tag Docker image
echo "Step 2: Building Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" . || exit 1

# Step 3: Push Docker image to Artifact Registry
echo "Step 3: Pushing Docker image: ${IMAGE_NAME}"
docker push "${IMAGE_NAME}" || exit 1

gcloud run jobs deploy "${JOB_NAME}" \
  --region="${REGION}" \
  --memory="${MEMORY}" \
  --cpu="${CPU}" \
  --image="${IMAGE_NAME}" \
  --task-timeout="${TASK_TIMEOUT}" \
  --set-env-vars="DB_CONNECTION_NAME=${DB_CONNECTION_INSTANCE},HIRE_USERNAME=crootonmaster@applygateway.com,DEBUG_SCREENSHOT_BUCKET=recruitment-engine-cvs-sp-260625,SE_SHM_SIZE=2G" \
  --set-secrets="HIRE_PASSWORD=hire-password:latest,DB_USER=db-user:latest,DB_PASSWORD=db-password:latest,DB_NAME=db-name:latest" \
  --set-cloudsql-instances="${DB_CONNECTION_INSTANCE}" \
  --service-account="screenshot-runner@intelligent-recruitment-engine.iam.gserviceaccount.com" \
  || exit 1

echo "✅ Job '${JOB_NAME}' deployed."
echo "👉 To run it: gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
echo "🔍 To view logs: use Cloud Logging and filter by Cloud Run Job: ${JOB_NAME}"
