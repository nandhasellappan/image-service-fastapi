import os
from typing import Optional, Set
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "local")
    
    # AWS Configuration
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_access_key_id: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # LocalStack specific
    localstack_endpoint: Optional[str] = os.getenv("LOCALSTACK_ENDPOINT")
    
    # S3 Configuration
    s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "image-storage-bucket")
    
    # DynamoDB Configuration
    dynamodb_table_name: str = os.getenv("DYNAMODB_TABLE_NAME", "ImageMetadata")

    # Application
    app_name: str = "Image Service Application"
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    # Simple token secret for API authorization (keep secure in prod)
    api_token: Optional[str] = os.getenv("API_TOKEN")
    
    # File validation
    allowed_extensions: Set[str] = {"jpg", "jpeg", "png", "gif", "webp"}
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    
    @property
    def is_localstack(self) -> bool:
        return self.environment == "local" and (
            bool(self.localstack_endpoint) or "LOCALSTACK_HOSTNAME" in os.environ
        )
    
    @property
    def endpoint_url(self) -> Optional[str]:
        if not self.is_localstack:
            return None
        if self.localstack_endpoint:
            return self.localstack_endpoint
        # Fallback to LOCALSTACK_HOSTNAME provided by LocalStack Lambda environment
        if "LOCALSTACK_HOSTNAME" in os.environ:
            return f"http://{os.environ['LOCALSTACK_HOSTNAME']}:4566"
        # Useful when LocalStack runs on host and container can reach host via this name (Docker Desktop)
        if os.getenv("USE_HOST_DOCKER_INTERNAL", "false").lower() == "true":
            return "http://host.docker.internal:4566"
        return None
    
    model_config = SettingsConfigDict(case_sensitive=False)

# Set the environment variables manually
# os.environ["ENVIRONMENT"] = "local"
# os.environ["LOCALSTACK_ENDPOINT"] = "http://localhost:4566"
# os.environ["S3_BUCKET_NAME"] = "image-storage-bucket"
# os.environ["DYNAMODB_TABLE_NAME"] = "ImageMetadata"

settings = Settings()
