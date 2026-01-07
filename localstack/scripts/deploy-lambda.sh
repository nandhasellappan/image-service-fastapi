#!/bin/bash
set -e

echo "Deploying Lambda function..."

ENDPOINT="http://localhost:4566"
AWS_CMD="aws.exe"

# Navigate to parent directory where zip file is
cd ..

# Verify zip exists
if [ ! -f "lambda_function.zip" ]; then
    echo "✗ ERROR: lambda_function.zip not found"
    exit 1
fi

echo "✓ Found lambda_function.zip ($(du -h lambda_function.zip | cut -f1))"

# Wait for LocalStack to be ready
sleep 2

# Delete existing function if it exists
echo "Removing existing function (if any)..."
$AWS_CMD --endpoint-url=$ENDPOINT lambda delete-function \
    --function-name "$FUNCTION_NAME" 2>/dev/null || true

# Create Lambda function
echo "Creating Lambda function..."
$AWS_CMD --endpoint-url=$ENDPOINT lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.11 \
    --handler lambda_handler.handler \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --zip-file fileb://lambda_function.zip \
    --timeout 30 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=local,LOCALSTACK_ENDPOINT=$ENDPOINT,S3_BUCKET_NAME=image-storage-bucket,DYNAMODB_TABLE_NAME=image-metadata,AWS_REGION=$REGION,AWS_ACCESS_KEY_ID=test,AWS_SECRET_ACCESS_KEY=test}" \
    --output text > /dev/null

echo "✓ Lambda function created successfully"

cd localstack
