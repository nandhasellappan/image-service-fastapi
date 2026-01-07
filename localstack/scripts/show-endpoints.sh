#!/bin/bash

if [ -f ".api_id" ]; then
    API_ID=$(cat .api_id | tr -d '\r')
else
    echo "Error: API ID not found"
    exit 1
fi

BASE_URL="http://localhost:4566/restapis/$API_ID/dev/_user_request_"

echo ""
echo "API Endpoint: $BASE_URL"
echo ""
echo "Test Commands:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Health:  curl $BASE_URL/health"
echo "Root:    curl $BASE_URL/"
echo "Upload:  curl -X POST $BASE_URL/api/v1/images -F 'file=@test.jpg'"
echo "List:    curl $BASE_URL/api/v1/images"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
