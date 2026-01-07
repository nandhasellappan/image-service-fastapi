#!/bin/bash
set -e

echo "Initializing AWS resources in LocalStack..."

# Wait for LocalStack to be ready
sleep 10

REGION="us-east-1"
FUNCTION_NAME="image-service-lambda"
API_NAME="image-service-api"

# ============================================
# S3 BUCKET CREATION
# ============================================
echo "Creating S3 bucket..."
awslocal s3 mb s3://image-storage-bucket || echo "Bucket already exists"

awslocal s3api put-bucket-cors \
    --bucket image-storage-bucket \
    --cors-configuration '{
      "CORSRules": [{
        "AllowedOrigins": ["*"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
        "AllowedHeaders": ["*"]
      }]
    }'

echo "✓ S3 bucket created"

# ============================================
# DYNAMODB TABLE CREATION
# ============================================
echo "Creating DynamoDB table..."
awslocal dynamodb create-table \
    --table-name ImageMetadata \
    --attribute-definitions \
        AttributeName=image_id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=created_at,AttributeType=S \
    --key-schema AttributeName=image_id,KeyType=HASH \
    --global-secondary-indexes \
        "[{
            \"IndexName\": \"UserIdIndex\",
            \"KeySchema\": [{\"AttributeName\":\"user_id\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}],
            \"Projection\":{\"ProjectionType\":\"ALL\"}
        }]" \
    --billing-mode PAY_PER_REQUEST || echo "Table already exists"

echo "✓ DynamoDB table created"

# ============================================
# IAM ROLE FOR LAMBDA
# ============================================

ROLE_NAME="image-service-lambda-role"
POLICY_NAME="lambda-s3-dynamodb-policy"
ROLE_ARN="arn:aws:iam::000000000000:role/${ROLE_NAME}"

echo "Creating IAM role for Lambda (if missing)..."

# Create role (ignore if already exists)

awslocal iam create-role \
  --role-name "${ROLE_NAME}" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || true

# Attach policy to role

awslocal iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name "${POLICY_NAME}" \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Effect\": \"Allow\",
        \"Action\": [
          \"s3:GetObject\",
          \"s3:PutObject\",
          \"s3:DeleteObject\",
          \"s3:ListBucket\"
        ],
        \"Resource\": [
          \"arn:aws:s3:::image-storage-bucket\",
          \"arn:aws:s3:::image-storage-bucket/*\"
        ]
      },
      {
        \"Effect\": \"Allow\",
        \"Action\": [
          \"dynamodb:PutItem\",
          \"dynamodb:GetItem\",
          \"dynamodb:DeleteItem\",
          \"dynamodb:UpdateItem\",
          \"dynamodb:Query\",
          \"dynamodb:Scan\"
        ],
        \"Resource\": [
          \"arn:aws:dynamodb:${REGION}:000000000000:table/ImageMetadata\",
          \"arn:aws:dynamodb:${REGION}:000000000000:table/ImageMetadata/index/*\"
        ]
      }
    ]
  }"

# Attach AWSLambdaBasicExecutionRole for logging
awslocal iam attach-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# ============================================
# VALIDATE LAMBDA FUNCTION ZIP FILE 
# ============================================

ZIP_PATH="/tmp/lambda_function.zip"

if [ ! -f "$ZIP_PATH" ]; then
  echo "✗ ERROR: lambda_function.zip not found at $ZIP_PATH"
  exit 1
fi

# ============================================
# LAMBDA FUNCTION CREATION
# ============================================
echo "Creating Lambda function..."

# Delete existing function if exists
awslocal lambda delete-function \
    --function-name "$FUNCTION_NAME" 2>/dev/null || true

# Create Lambda function
awslocal lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.11 \
    --handler lambda_handler.handler \
    --role "$ROLE_ARN" \
    --zip-file "fileb://$ZIP_PATH" \
    --timeout 30 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=local,LOCALSTACK_ENDPOINT=http://host.docker.internal:4566,S3_BUCKET_NAME=image-storage-bucket,DYNAMODB_TABLE_NAME=ImageMetadata,AWS_REGION=$REGION,LOG_LEVEL=DEBUG,DEBUG=true}"

echo "✓ Lambda function created"


# ============================================
# API GATEWAY CREATION
# ============================================
echo "Creating API Gateway..."

# Create REST API
API_ID=$(awslocal apigateway create-rest-api \
    --name "$API_NAME" \
    --query 'id' --output text)

echo "✓ API Gateway created: $API_ID"

# Get root resource
ROOT_ID=$(awslocal apigateway get-resources \
    --rest-api-id $API_ID \
    --query 'items[0].id' --output text)

# Create proxy resource
RESOURCE_ID=$(awslocal apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $ROOT_ID \
    --path-part '{proxy+}' \
    --query 'id' --output text)

# Setup methods for root
awslocal apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $ROOT_ID \
    --http-method ANY \
    --authorization-type NONE

awslocal apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $ROOT_ID \
    --http-method ANY \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:$FUNCTION_NAME/invocations"

# Setup methods for proxy
awslocal apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method ANY \
    --authorization-type NONE

awslocal apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method ANY \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:$FUNCTION_NAME/invocations"

# Deploy API
awslocal apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name dev

echo "✓ API Gateway deployed"

# ============================================
# DISPLAY ENDPOINTS
# ============================================
BASE_URL="http://localhost:4566/restapis/$API_ID/dev/_user_request_"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ LocalStack setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "API Endpoint: $BASE_URL"
echo ""
echo "Test Commands:"
echo "  Health:  curl $BASE_URL/health"
echo "  Root:    curl $BASE_URL/"
echo "  Upload:  curl -X POST $BASE_URL/api/v1/images -F 'file=@test.jpg'"
echo "  List:    curl $BASE_URL/api/v1/images"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
