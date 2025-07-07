#!/bin/bash
set -e

# Configuration
BASE_TAG="v3"
REGION="europe-west2"
MEMORY="8Gi"
CPU="2"
TASK_TIMEOUT="1800s"
DB_CONNECTION_INSTANCE="intelligent-recruitment-engine:europe-west2:recruitment-db-main"
SERVICE_ACCOUNT="ingestion-job-sa@intelligent-recruitment-engine.iam.gserviceaccount.com"
REPO="europe-west2-docker.pkg.dev/intelligent-recruitment-engine/recruitment-engine-repo"

# Generate timestamp-based tag and job name
TIMESTAMP=$(date +"%Y%m%d-%H%M")
JOB_TAG="${BASE_TAG}-${TIMESTAMP}"
JOB_NAME="daily-cvs-job-${JOB_TAG}"
IMAGE_NAME="${REPO}/${JOB_NAME}:${JOB_TAG}"

echo "🛠 Step 1: Preparing workspace..."
cd ~/ || exit 1
rm -rf loop-cvs
git clone https://github.com/crootonSMP/loop-pull-hi-cvs.git loop-cvs || exit 1
cd loop-cvs || exit 1

echo "🐳 Step 2: Building Docker image: ${IMAGE_NAME}"
docker build --no-cache -t "${IMAGE_NAME}" . || exit 1

echo "📤 Step 3: Pushing Docker image: ${IMAGE_NAME}"
docker push "${IMAGE_NAME}" || exit 1

echo "🚀 Step 4: Deploying Cloud Run Job: ${JOB_NAME}"
gcloud run jobs deploy "${JOB_NAME}" \
  --region="${REGION}" \
  --image="${IMAGE_NAME}" \
  --memory="${MEMORY}" \
  --cpu="${CPU}" \
  --task-timeout="${TASK_TIMEOUT}" \
  --set-env-vars="DB_CONNECTION_NAME=${DB_CONNECTION_INSTANCE}" \
  --set-env-vars="HIRE_USERNAME=crootonmaster@applygateway.com" \
  --set-env-vars="CV_BUCKET_NAME=intelligent-recruitment-cvs" \
  --set-secrets="HIRE_PASSWORD=hire-password:latest" \
  --set-secrets="DB_USER=db-user:latest" \
  --set-secrets="DB_PASSWORD=db-password:latest" \
  --set-secrets="DB_NAME=db-name:latest" \
  --set-secrets="HIRE_API_KEY=hire-api-key:latest" \
  --set-cloudsql-instances="${DB_CONNECTION_INSTANCE}" \
  --service-account="${SERVICE_ACCOUNT}" \
  || exit 1

echo "✅ Job '${JOB_NAME}' deployed successfully."
echo "👉 To run it:     gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
echo "🔍 To view logs:  gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}' --limit=50"
