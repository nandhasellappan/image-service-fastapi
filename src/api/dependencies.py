from fastapi import Depends, HTTPException, status
from services.s3_service import S3Service
from services.dynamodb_service import DynamoDBService


def get_s3_service() -> S3Service:
    """Dependency for S3 service."""
    return S3Service()


def get_dynamodb_service() -> DynamoDBService:
    """Dependency for DynamoDB service."""
    return DynamoDBService()