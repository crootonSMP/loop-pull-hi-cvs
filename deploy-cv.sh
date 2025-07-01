#!/bin/bash

set -e  # Exit on error

# Define common variables for easier management and consistency
JOB_TAG="latest"
JOB_NAME="daily-hire-screenshot-job-v01-01" # Using the job name from your latest successful build output
IMAGE_NAME="europe-west2-docker.pkg.dev/intelligent-recruitment-engine/recruitment-engine-repo/${JOB_NAME}:${JOB_TAG}"
REGION="europe-west2"
MEMORY="1Gi" # Adjust as needed based on browser memory usage
CPU="1"
TASK_TIMEOUT="1800" # 30 minutes timeout

# DB Connection details (needs to match your Cloud SQL instance)
# These are still passed as environment variables/secrets for consistency with the broader project setup,
# even if this specific screenshot script doesn't directly use the DB.
DB_CONNECTION_INSTANCE="intelligent-recruitment-engine:europe-west2:recruitment-db-main"

# Step 1: Prepare workspace
echo "Step 1: Preparing workspace..."
cd ~/ || exit 1
rm -rf loop-cvs # Use the new distinct folder name for this job's repo
git clone https://github.com/crootonSMP/loop-pull-hi-cvs.git loop-cvs || exit 1
cd ~/loop-cvs || exit 1

echo "Current directory contents:"
ls -l
echo "Dockerfile content (snippet):"
head -n 20 Dockerfile
echo "requirements.txt content:"
cat requirements.txt
echo "⛽️⛽️⛽️⛽️⛽️⛽️"
# Step 2: Build and tag the Docker image
echo "Step 2: Building and tagging Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" . || exit 1

# Step 3: Push the Docker image to Artifact Registry
echo "Step 3: Pushing Docker image: ${IMAGE_NAME}"
docker push "${IMAGE_NAME}" || exit 1

# Step 4: Create the Cloud Run Job (or update if it exists)
echo "Step 4: Creating/Updating Cloud Run Job: ${JOB_NAME}"
gcloud run jobs deploy "${JOB_NAME}" \
  --region="${REGION}" \
  --memory="${MEMORY}" \
  --cpu="${CPU}" \
  --image="${IMAGE_NAME}" \
  --task-timeout="${TASK_TIMEOUT}" \
  --set-env-vars="DB_CONNECTION_NAME=${DB_CONNECTION_INSTANCE},HIRE_USERNAME=crootonmaster@applygateway.com" \
  --set-secrets="HIRE_PASSWORD=hire-password:latest,DB_USER=db-user:latest,DB_PASSWORD=db-password:latest,DB_NAME=db-name:latest" \
  --set-cloudsql-instances="${DB_CONNECTION_INSTANCE}" \
  || exit 1

# --- REMOVED THE JOB READINESS CHECK LOOP ---
# This loop is only relevant if you immediately execute the job after deployment and want to wait for its completion.
# The `gcloud run jobs deploy` command itself already confirms if the job *definition* was deployed successfully.
# --- END REMOVED SECTION ---

echo "Deployment script completed. Job '${JOB_NAME}' is deployed and ready for execution."
echo "To manually execute this job, use: gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
echo "To view execution logs, go to Cloud Logging and filter by Cloud Run Job: ${JOB_NAME}"
