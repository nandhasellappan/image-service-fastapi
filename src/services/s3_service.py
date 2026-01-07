"""
Service module for interacting with Amazon S3 for file storage operations.
"""
import boto3
from typing import BinaryIO
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class S3Service:
    """
    Service class for interacting with AWS S3.
    Handles file uploads, deletions, existence checks, and presigned URL generation.
    """
    def __init__(self):
        """
        Initialize the S3 service.

        Sets up the Boto3 client for S3 interactions using settings from config.
        """
        logger.info(f"Initializing S3Service for bucket: {settings.s3_bucket_name}")
        self.client = boto3.client(
            's3',
            endpoint_url=settings.endpoint_url,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        self.bucket_name = settings.s3_bucket_name
    
    def upload_file(self, file_key: str, file_obj: BinaryIO, content_type: str) -> str:
        """
        Upload a file to the S3 bucket.

        Args:
            file_key (str): The key (path) where the file will be stored in the bucket.
            file_obj (BinaryIO): The file-like object to upload.
            content_type (str): The MIME type of the file.

        Returns:
            str: The S3 URI of the uploaded file (e.g., s3://bucket/key).
        """
        logger.info(f"Uploading to S3: {file_key}")
        resp = self.client.put_object(
            Bucket=self.bucket_name,
            Key=file_key,
            Body=file_obj,
            ContentType=content_type
        )
        s3_url = f"s3://{self.bucket_name}/{file_key}"
        etag = resp.get('ETag') if isinstance(resp, dict) else None
        logger.info(f"Upload successful: {s3_url}", extra={'etag': etag})
        return s3_url
    
    def get_presigned_url(self, file_key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for retrieving a file.

        Args:
            file_key (str): The key of the file in S3.
            expiration (int): Time in seconds until the URL expires. Defaults to 3600.

        Returns:
            str: The presigned URL.
        """
        logger.debug(f"Generating presigned URL for: {file_key}")
        url = self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': file_key},
            ExpiresIn=expiration
        )
        
        # Fix for LocalStack: 'host.docker.internal' is reachable from container but not always from host browser.
        # Replace it with 'localhost' for client-side accessibility.
        if settings.is_localstack and "host.docker.internal" in url:
            url = url.replace("host.docker.internal", "localhost")
        return url
    
    def delete_file(self, file_key: str) -> None:
        """
        Delete a file from the S3 bucket.

        Args:
            file_key (str): The key of the file to delete.
        """
        logger.info(f"Deleting from S3: {file_key}")
        resp = self.client.delete_object(Bucket=self.bucket_name, Key=file_key)
        logger.info(f"Deleted S3 object: {file_key}", extra={'response': resp})
    
    def file_exists(self, file_key: str) -> bool:
        """`
        Check if a file exists in the S3 bucket.

        Args:
            file_key (str): The key of the file to check.

        Returns:
            bool: True if the file exists, False otherwise.
        """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except:
            return False


s3_service = S3Service()
