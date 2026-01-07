"""
Local development server
"""
import uvicorn
import os
from utils.logger import get_logger

logger = get_logger(__name__)

if __name__ == "__main__":
    logger.info("Starting local development server on http://localhost:8000")
    logger.info("API docs available at http://localhost:8000/docs")

    # Set the environment variables manually
    os.environ["ENVIRONMENT"] = "local"
    os.environ["LOCALSTACK_ENDPOINT"] = "http://localhost:4566"
    os.environ["S3_BUCKET_NAME"] = "image-storage-bucket"
    os.environ["DYNAMODB_TABLE_NAME"] = "ImageMetadata"
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
