#!/bin/bash
set -e

echo "Setting up API Gateway..."

ENDPOINT="http://localhost:4566"
AWS_CMD="aws.exe"

# Get or create API
API_ID=$($AWS_CMD --endpoint-url=$ENDPOINT apigateway get-rest-apis \
    --query "items[?name=='$API_NAME'].id" --output text | tr -d '\r')

if [ -z "$API_ID" ] || [ "$API_ID" == "None" ]; then
    API_ID=$($AWS_CMD --endpoint-url=$ENDPOINT apigateway create-rest-api \
        --name "$API_NAME" --query 'id' --output text | tr -d '\r')
    echo "✓ Created API Gateway: $API_ID"
else
    echo "✓ Using existing API Gateway: $API_ID"
fi

# Get root resource
ROOT_ID=$($AWS_CMD --endpoint-url=$ENDPOINT apigateway get-resources \
    --rest-api-id $API_ID --query 'items[0].id' --output text | tr -d '\r')

# Get or create proxy resource
RESOURCE_ID=$($AWS_CMD --endpoint-url=$ENDPOINT apigateway get-resources \
    --rest-api-id $API_ID --query "items[?path=='/{proxy+}'].id" --output text | tr -d '\r')

if [ -z "$RESOURCE_ID" ] || [ "$RESOURCE_ID" == "None" ]; then
    RESOURCE_ID=$($AWS_CMD --endpoint-url=$ENDPOINT apigateway create-resource \
        --rest-api-id $API_ID \
        --parent-id $ROOT_ID \
        --path-part '{proxy+}' \
        --query 'id' --output text | tr -d '\r')
    echo "✓ Created proxy resource"
else
    echo "✓ Using existing proxy resource"
fi

# Setup methods
echo "✓ Configuring API methods"

# Root ANY method
$AWS_CMD --endpoint-url=$ENDPOINT apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $ROOT_ID \
    --http-method ANY \
    --authorization-type NONE > /dev/null 2>&1 || true

$AWS_CMD --endpoint-url=$ENDPOINT apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $ROOT_ID \
    --http-method ANY \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:$FUNCTION_NAME/invocations" > /dev/null 2>&1 || true

# Proxy ANY method
$AWS_CMD --endpoint-url=$ENDPOINT apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method ANY \
    --authorization-type NONE > /dev/null 2>&1 || true

$AWS_CMD --endpoint-url=$ENDPOINT apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method ANY \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:$FUNCTION_NAME/invocations" > /dev/null

# Deploy API
echo "✓ Deploying API to 'dev' stage"
$AWS_CMD --endpoint-url=$ENDPOINT apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name dev > /dev/null

# Save API ID
echo $API_ID > .api_id

echo "✓ API Gateway setup complete"
