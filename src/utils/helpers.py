import uuid
from datetime import datetime
from typing import Optional
import io
from PIL import Image
from config import settings


def generate_image_id() -> str:
    """Generate unique image ID."""
    return f"img_{uuid.uuid4().hex[:12]}"


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def generate_s3_key(user_id: str, image_id: str, file_extension: str) -> str:
    """
    Generate S3 key for image storage.
    
    Args:
        user_id: User ID
        image_id: Image ID
        file_extension: File extension
        
    Returns:
        str: S3 key path
    """
    return f"images/{user_id}/{image_id}.{file_extension}"


def validate_file_extension(filename: str) -> Optional[str]:
    """
    Validate and extract file extension.
    
    Args:
        filename: Name of the file
        
    Returns:
        str or None: Valid extension or None
    """
    if "." not in filename:
        return None
    
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension in settings.allowed_extensions:
        return extension
    return None


def validate_image_content(file_content: bytes) -> bool:
    """
    Validate that file content is actually an image.
    
    Args:
        file_content: File bytes
        
    Returns:
        bool: True if valid image
    """
    try:
        with Image.open(io.BytesIO(file_content)) as img:
            return img.format.lower() in ["jpeg", "png", "gif", "webp"]
    except Exception:
        return False