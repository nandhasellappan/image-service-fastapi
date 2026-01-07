"""
Pydantic schemas for the Image Service API.
Defines request and response models for image operations including uploads,
retrievals, deletions, and health checks.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ImageCategory(str, Enum):
    """Image category enumeration."""
    PROFILE = "profile"
    POST = "post"
    STORY = "story"
    REEL = "reel"


class ImageUploadRequest(BaseModel):
    """Schema for image upload metadata."""
    user_id: str = Field(..., description="User ID who uploads the image", min_length=1)
    title: str = Field(..., description="Image title", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Image description", max_length=1000)
    category: ImageCategory = Field(..., description="Image category")
    tags: Optional[List[str]] = Field(default=[], description="Image tags for searchability")
    is_public: bool = Field(default=True, description="Whether image is public or private")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_id": "user123",
            "title": "Beautiful Sunset",
            "description": "A stunning sunset at the beach",
            "category": "post",
            "tags": ["sunset", "beach", "nature"],
            "is_public": True
        }
    })


class ImageMetadata(BaseModel):
    """Schema for image metadata response."""
    # Essential mandatory fields
    filename: str = Field(..., description="Original filename")
    s3_url: str = Field(..., description="S3 URL of the uploaded image")
    
    # Optional fields with defaults
    image_id: Optional[str] = Field(None, description="Unique image identifier")
    user_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[ImageCategory] = None
    tags: List[str] = Field(default_factory=list)
    is_public: bool = True
    file_size: Optional[int] = Field(None, description="File size in bytes")
    content_type: Optional[str] = Field(None, description="MIME type of the image")
    s3_key: Optional[str] = Field(None, description="S3 object key")
    uploaded_at: Optional[str] = Field(None, description="Upload timestamp in ISO format")
    presigned_url: Optional[str] = Field(None, description="Presigned URL for temporary access")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "filename": "sunset.jpg",
            "s3_url": "s3://bucket/images/sunset.jpg",
            "image_id": "img_123abc",
            "user_id": "user123",
            "title": "Beautiful Sunset",
            "file_size": 2048576,
            "content_type": "image/jpeg"
        }
    })


class ImageUploadResponse(BaseModel):
    """Schema for image upload response."""
    success: bool = Field(default=True, description="Upload success status")
    message: str = Field(default="Upload successful", description="Response message")
    data: ImageMetadata
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "message": "Image uploaded successfully",
            "data": {
                "filename": "sunset.jpg",
                "s3_url": "s3://bucket/images/sunset.jpg"
            }
        }
    })


class ImageListResponse(BaseModel):
    """Schema for image list response."""
    success: bool = True
    count: int = Field(..., description="Number of images returned")
    data: List[ImageMetadata]
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "count": 2,
            "data": [
                {
                    "filename": "sunset.jpg",
                    "s3_url": "s3://bucket/images/sunset.jpg"
                }
            ]
        }
    })


class UploadData(BaseModel):
    """Schema for basic upload data without S3 details."""
    image_id: str
    filename: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None


class ImageUploadBasicResponse(BaseModel):
    """Minimal upload response that doesn't expose S3 fields."""
    success: bool = Field(default=True, description="Upload success status")
    message: str = Field(default="Upload successful", description="Response message")
    data: UploadData

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "message": "Image uploaded successfully",
            "data": {
                "image_id": "img_123abc",
                "filename": "sunset.jpg",
                "content_type": "image/jpeg",
                "file_size": 2048576
            }
        }
    })


class ImageUploadResult(BaseModel):
    """Schema for individual upload result in a bulk operation."""
    image_id: str
    filename: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    error: Optional[str] = None


class ImageUploadMultipleBasicResponse(BaseModel):
    """Response for multiple uploads."""
    success: bool = Field(default=True, description="Upload overall success status")
    message: str = Field(default="Upload processed", description="Response message")
    data: List[ImageUploadResult]

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "message": "2 files processed",
            "data": [
                {"image_id":"img_1","filename":"a.jpg","content_type":"image/jpeg","file_size":1024},
                {"image_id":"img_2","filename":"b.jpg","content_type":"image/jpeg","file_size":2048}
            ]
        }
    })


class ImageDeleteResponse(BaseModel):
    """Schema for image deletion response."""
    success: bool
    message: str
    image_id: str
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "message": "Image deleted successfully",
            "image_id": "img_123abc"
        }
    })


class BulkDeleteRequest(BaseModel):
    """Schema for bulk image deletion request."""
    user_id: str
    image_ids: List[str]

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_id": "user123",
            "image_ids": ["img_1", "img_2"]
        }
    })


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    success: bool = False
    error: str = Field(..., description="Error message")
    details: Optional[str] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error": "Image not found",
            "details": "No image exists with the provided ID"
        }
    })


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str = Field(..., description="Service status")
    timestamp: str
    services: dict = Field(..., description="Status of dependent services")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "healthy",
            "timestamp": "2025-12-31T08:00:00Z",
            "services": {
                "s3": "connected",
                "dynamodb": "connected"
            }
        }
    })
