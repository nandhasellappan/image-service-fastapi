#!/bin/bash
set -e

echo "========================================="
echo "Deploying to LocalStack..."
echo "========================================="

ENDPOINT="http://localhost:4566"

# Set dummy credentials for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Configuration
export FUNCTION_NAME="image-service-lambda"
export API_NAME="image-service-lambda"
export ENDPOINT
export REGION="us-east-1"

# Use aws.exe for Windows
export AWS_CMD="aws.exe"

# Run build script
echo "Step 1: Building Lambda package..."
bash scripts/build.sh "$@"

# Run Lambda deployment
echo "Step 2: Deploying Lambda function..."
bash scripts/deploy-lambda.sh

# Run API Gateway deployment
echo "Step 3: Setting up API Gateway..."
bash scripts/deploy-api.sh

echo "========================================="
echo "Deployment Complete!"
echo "========================================="
bash scripts/show-endpoints.sh
