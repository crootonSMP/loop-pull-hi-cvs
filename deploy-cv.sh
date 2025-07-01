#!/bin/bash

set -e  # Exit on error

# Define common variables for easier management and consistency
JOB_TAG="latest" # Simple tag for the single consolidated job
JOB_NAME="daily-hire-screenshot-job" # Name for the new screenshot job
IMAGE_NAME="europe-west2-docker.pkg.dev/intelligent-recruitment-engine/recruitment-engine-repo/${JOB_NAME}:${JOB_TAG}"
REGION="europe-west2"
MEMORY="1Gi" # Adjust as needed based on browser memory usage
CPU="1"
TASK_TIMEOUT="1800" # 30 minutes timeout

# DB Connection details (if still needed by the base image, otherwise can be removed)
# Although the new script doesn't interact with DB directly, the environment might still expect it
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
head -n 20 Dockerfile # Show more lines to include Chrome installation
echo "requirements.txt content:"
cat requirements.txt

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
  --memory "${MEMORY}" \
  --cpu "${CPU}" \
  --image="${IMAGE_NAME}" \
  --task-timeout="${TASK_TIMEOUT}" \
  --set-env-vars="HIRE_USERNAME=crootonmaster@applygateway.com" \
  --set-secrets="HIRE_PASSWORD=hire-password:latest" \
  # If DB_CONNECTION_NAME is truly no longer needed by the *entrypoint script itself*,
  # you could remove it, but often base environments still implicitly rely on it.
  # For now, keeping it consistent with previous setup if no issues arise.
  --set-env-vars="DB_CONNECTION_NAME=${DB_CONNECTION_INSTANCE},HIRE_USERNAME=crootonmaster@applygateway.com" \
  --set-cloudsql-instances="${DB_CONNECTION_INSTANCE}" \
  || exit 1

echo "Waiting for job '${JOB_NAME}' to be ready..."
for i in {1..10}; do
    JOB_STATUS=$(gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --format="value(status.latestCreatedExecution.completionTime)" 2>/dev/null)
    if [ -n "${JOB_STATUS}" ]; then
        echo "Job '${JOB_NAME}' is ready."
        break
    else
        echo "Job '${JOB_NAME}' not yet ready (attempt ${i}/10). Waiting 15 seconds..."
        sleep 15
    fi
    if [ "$i" -eq 10 ]; then
        echo "Error: Job '${JOB_NAME}' did not become ready after multiple attempts. Manual check required."
        exit 1
    fi
done

echo "Deployment script completed. Job '${JOB_NAME}' is ready for execution."
