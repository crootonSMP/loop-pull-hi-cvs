#!/bin/bash
set -e

# Automatically increment JOB_TAG based on the latest tag
CURRENT_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v8-0")
IFS='-' read -r prefix number <<< "$CURRENT_TAG"
NEW_NUMBER=$((number + 1))
JOB_TAG="v8-${NEW_NUMBER}"
JOB_NAME="x-daily-hire-screenshot-job-${JOB_TAG}"
IMAGE_NAME="europe-west2-docker.pkg.dev/intelligent-recruitment-engine/recruitment-engine-repo/${JOB_NAME}:${JOB_TAG}
REGION="europe-west2"
MEMORY="8Gi"
CPU="2"
TASK_TIMEOUT="1800s"
DB_CONNECTION_INSTANCE="intelligent-recruitment-engine:europe-west2:recruitment-db-main"

echo "Step 1: Preparing workspace..."
cd ~/ || exit 1
rm -rf loop-cvs
git clone https://github.com/crootonSMP/loop-pull-hi-cvs.git loop-cvs || exit 1
cd loop-cvs || exit 1

echo "Step 2: Building Docker image: ${IMAGE_NAME}"
docker build --no-cache --memory 4g --shm-size 2g -t "${IMAGE_NAME}" . || exit 1

echo "Step 3: Pushing Docker image: ${IMAGE_NAME}"
docker push "${IMAGE_NAME}" || exit 1

echo "Step 4: Deploying Cloud Run Job: ${JOB_NAME}"
gcloud run jobs deploy "${JOB_NAME}" \
  --region="${REGION}" \
  --image="${IMAGE_NAME}" \
  --memory="${MEMORY}" \
  --cpu="${CPU}" \
  --task-timeout="${TASK_TIMEOUT}" \
  --set-env-vars="DB_CONNECTION_NAME=${DB_CONNECTION_INSTANCE}" \
  --set-env-vars="HIRE_USERNAME=crootonmaster@applygateway.com" \
  --set-env-vars="DEBUG_SCREENSHOT_BUCKET=recruitment-engine-cvs-sp-260625" \
  --set-env-vars="CV_BUCKET=recruitment-engine-cvs-sp-260625" \  # Updated bucket
  --set-env-vars="SE_SHM_SIZE=2g" \
  --set-secrets="HIRE_PASSWORD=hire-password:latest" \
  --set-secrets="DB_USER=db-user:latest" \
  --set-secrets="DB_PASSWORD=db-password:latest" \
  --set-secrets="DB_NAME=db-name:latest" \
  --set-secrets="REACT_APP_CV_DOWNLOAD_API_KEY=cv-download-api-key:latest" \
  --set-cloudsql-instances="${DB_CONNECTION_INSTANCE}" \
  --service-account="screenshot-runner@intelligent-recruitment-engine.iam.gserviceaccount.com" \
  || exit 1

echo "✅ Job '${JOB_NAME}' deployed successfully."
echo "👉 To run it: gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
echo "🔍 To view logs: gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}' --limit=50"
