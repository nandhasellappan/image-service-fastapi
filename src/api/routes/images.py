"""
API routes for image management.
Handles image uploads, retrieval, listing, and deletion.
"""
import traceback
import uuid
import json
import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form
from config import settings
from datetime import datetime
from services.s3_service import s3_service
from services.dynamodb_service import dynamodb_service
from models.schemas import (
    ImageMetadata,
    ImageUploadMultipleBasicResponse,
    ImageUploadResult,
    BulkDeleteRequest,
)
from utils.logger import get_logger
from fastapi import Depends, Header


logger = get_logger(__name__)
router = APIRouter()


def _sanitize_image_id(image_id: str) -> str:
    """Normalize image_id path input.
    Handles cases where clients send values like '{image_id=...}' or include surrounding braces.
    """
    if not image_id:
        return image_id
    val = image_id
    # strip surrounding braces
    if val.startswith('{') and val.endswith('}'):
        val = val[1:-1]
    # handle 'image_id=...' style (e.g. some clients/templates)
    if val.startswith('image_id='):
        val = val.split('=', 1)[1]
    return val


@router.post("/images", response_model=ImageUploadMultipleBasicResponse)
async def upload_image(
    files: List[UploadFile] = File(...),
    user_id: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_public: bool = Form(True),
):
    """
    Upload multiple images to S3 and store metadata in DynamoDB.

    Args:
        files (List[UploadFile]): List of image files to upload.
        user_id (str): ID of the user uploading the images.
        title (Optional[str]): Title for the images.
        description (Optional[str]): Description for the images.
        category (Optional[str]): Category of the images.
        tags (Optional[str]): Comma-separated tags.
        is_public (bool): Visibility status.

    Returns:
        ImageUploadMultipleBasicResponse: Result of the upload operation.
    """
    logger.info(f"Upload request: {len(files)} file(s) for user: {user_id}")
    try:
        # validate inputs
        if not user_id or not user_id.strip():
            raise HTTPException(status_code=400, detail="user_id is required")

        MAX_FILES = 10
        if len(files) == 0:
            raise HTTPException(status_code=400, detail="At least one file is required")
        if len(files) > MAX_FILES:
            raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES} files allowed")

        tags_list: List[str] = []
        if tags:
            tags_list = [t.strip() for t in tags.split(',') if t.strip()]

        results: List[ImageUploadResult] = []
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        for file in files:
            try:
                if not file.content_type or not file.content_type.startswith('image/'):
                    raise ValueError("File must be an image")

                # sanitize filename
                orig_name = os.path.basename(file.filename or "")
                if not orig_name:
                    raise ValueError("Invalid filename")

                ext = orig_name.rsplit('.', 1)[-1].lower() if '.' in orig_name else ''
                if ext and settings.allowed_extensions and ext not in settings.allowed_extensions:
                    raise ValueError("File extension not allowed")

                content = await file.read()
                size = len(content)
                if size == 0:
                    raise ValueError("Empty file")
                if size > settings.max_file_size:
                    raise ValueError("File exceeds maximum allowed size")

                image_id = str(uuid.uuid4())
                file_key = f"images/{timestamp}_{image_id}_{orig_name}"

                # upload to S3 first
                s3_url = s3_service.upload_file(file_key, content, file.content_type)

                metadata = {
                    'image_id': image_id,
                    'user_id': user_id,
                    'title': title,
                    'description': description,
                    'category': category,
                    'tags': tags_list,
                    'is_public': bool(is_public),
                    'filename': orig_name,
                    'content_type': file.content_type,
                    'file_size': size,
                    's3_url': s3_url,
                    's3_key': file_key,
                    'upload_timestamp': timestamp,
                    'uploaded_at': datetime.utcnow().isoformat() + 'Z'
                }

                # store metadata; if DB write fails, remove S3 object
                try:
                    dynamodb_service.put_metadata(image_id, metadata)
                    results.append(ImageUploadResult(
                        image_id=image_id,
                        filename=orig_name,
                        content_type=file.content_type,
                        file_size=size,
                    ))
                except Exception as e:
                    # rollback S3
                    try:
                        s3_service.delete_file(file_key)
                    except Exception:
                        logger.warning(f"Failed to delete S3 object after DB failure: {file_key}")
                    raise
            except Exception as e:
                logger.warning(f"Upload failed for file {getattr(file,'filename',None)}: {e}")
                results.append(ImageUploadResult(
                    image_id=str(uuid.uuid4()),
                    filename=getattr(file, 'filename', 'unknown'),
                    error=str(e)
                ))

        # generate overall response
        success_overall = any(r.error is None for r in results)
        return {
            "success": success_overall,
            "message": f"{len([r for r in results if r.error is None])} files uploaded, {len([r for r in results if r.error])} failures",
            "data": [r.dict() for r in results]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/images/{image_id}", response_model=ImageMetadata)
def get_image(image_id: str):
    """
    Retrieve image metadata and a presigned URL.

    Args:
        image_id (str): Unique identifier of the image.

    Returns:
        ImageMetadata: Metadata of the requested image.
    """
    image_id = _sanitize_image_id(image_id)
    logger.info(f"Get image: {image_id}")
    metadata = dynamodb_service.get_metadata(image_id)
    if not metadata:
        logger.warning(f"Image not found: {image_id}")
        raise HTTPException(status_code=404, detail="Image not found")
    
    s3_key = metadata.get('s3_key') or metadata.get('filename') or image_id
    presigned_url = s3_service.get_presigned_url(s3_key)
    metadata['presigned_url'] = presigned_url
    return metadata


@router.delete("/images/{image_id}")
def delete_image(image_id: str):
    """
    Delete an image and its metadata.

    Args:
        image_id (str): Unique identifier of the image to delete.

    Returns:
        dict: Success message.
    """
    image_id = _sanitize_image_id(image_id)
    logger.info(f"Delete image: {image_id}")
    try:
        metadata = dynamodb_service.get_metadata(image_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Image not found")

        s3_key = metadata.get('s3_key') or metadata.get('filename') or image_id
        if not s3_service.file_exists(s3_key):
            raise HTTPException(status_code=404, detail="Image not found in S3")

        s3_service.delete_file(s3_key)
        dynamodb_service.delete_metadata(image_id)
        
        logger.info(f"Delete successful: {image_id}")
        return {"message": "Image deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/images")
def list_images(
    limit: int = 50,
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter"),
    filename_contains: Optional[str] = None,
    last_evaluated_key: Optional[str] = None,
):
    """
    List images with optional filtering and pagination.

    Args:
        limit (int): Maximum number of items to return.
        user_id (Optional[str]): Filter by user ID.
        category (Optional[str]): Filter by category.
        is_public (Optional[bool]): Filter by visibility.
        tags (Optional[str]): Filter by tags (comma-separated).
        filename_contains (Optional[str]): Filter by filename substring.
        last_evaluated_key (Optional[str]): Pagination token from previous response.

    Returns:
        dict: List of images and pagination key.
    """
    logger.info(f"List images (limit: {limit}) filters user_id={user_id} category={category} is_public={is_public}")
    try:
        tags_list: Optional[List[str]] = None
        if tags:
            tags_list = [t.strip() for t in tags.split(',') if t.strip()]

        eks = None
        if last_evaluated_key:
            try:
                eks = json.loads(last_evaluated_key)
            except Exception:
                eks = None

        resp = dynamodb_service.list_metadata(
            user_id=user_id,
            category=category,
            is_public=is_public,
            tags=tags_list,
            filename_contains=filename_contains,
            limit=limit,
            exclusive_start_key=eks,
        )

        items = resp.get('items', [])
        # Attach presigned URL for verification to each item when possible
        for it in items:
            try:
                s3_key = it.get('s3_key') or it.get('filename') or it.get('image_id')
                it['presigned_url'] = s3_service.get_presigned_url(s3_key)
            except Exception:
                logger.debug(f"Could not generate presigned URL for item: {it.get('image_id')}")

        lek = resp.get('last_evaluated_key')
        return {"images": items, "count": len(items), "last_evaluated_key": lek}
    except Exception as e:
        logger.error(f"List failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


_API_TOKEN_CACHE = None

def _get_api_token_from_secrets() -> str:
    """Fetch API token from AWS Secrets Manager with caching."""
    global _API_TOKEN_CACHE
    if _API_TOKEN_CACHE:
        return _API_TOKEN_CACHE

    secret_name = "image_service_api_token"
    region_name = settings.aws_region

    try:
        session = boto3.session.Session()
        # Check if running in LocalStack and adjust endpoint
        if settings.is_localstack:
            logger.debug(f"Connecting to Secrets Manager (LocalStack) at {settings.endpoint_url}")
            client = session.client(
                service_name='secretsmanager',
                region_name=region_name,
                endpoint_url=settings.endpoint_url,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )
        else:
            logger.debug("Connecting to AWS Secrets Manager")
            client = session.client(
                service_name='secretsmanager',
                region_name=region_name
            )

        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']

        logger.debug(f"Secret retrieved. Length: {len(secret)}")
        
        logger.info("Successfully retrieved API token from Secrets Manager")
        try:
            secret_dict = json.loads(secret)
            token = secret_dict.get('api_token')
            if not token:
                logger.warning("Secret JSON parsed but 'api_token' key missing. Using full secret string.")
                token = secret
            else:
                logger.debug("Successfully parsed 'api_token' from JSON")
        except json.JSONDecodeError:
            logger.warning("Secret is not valid JSON. Using raw secret string.")
            token = secret        
            
        _API_TOKEN_CACHE = token
        return token
    except ClientError as e:
        logger.error(f"Failed to fetch API token from Secrets Manager: {e}", exc_info=True)
        # Fallback to static config if secret fetch fails
        return settings.api_token
    except Exception as e:
        logger.error(f"Unexpected error in _get_api_token_from_secrets: {e}", exc_info=True)
        return settings.api_token


def _get_token_user(authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)) -> str:
    """Simple token parsing: accept Bearer '<user_id>:<secret>' or x-api-key '<user_id>:<secret>' or admin secret.
    Returns user_id on success, raises HTTPException(401) on failure.
    """
    # TODO: Implement JWT token verification later
    logger.debug(f"Authenticating request. Auth Header: {bool(authorization)}, X-API-Key: {bool(x_api_key)}")
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    elif x_api_key:
        token = x_api_key

    if not token:
        logger.warning("Authentication failed: Missing token")
        raise HTTPException(status_code=401, detail="Unauthorized")

    api_token = _get_api_token_from_secrets()
    
    if not api_token:
        logger.error("Authentication failed: System API token not configured (Secrets Manager fetch failed and no fallback set)")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # token format: 'user_id:secret' or single secret for admin    
    if ":" in token:
        user, secret = token.split(":", 1)
        if secret != api_token:
            logger.warning(f"Authentication failed: Invalid secret for user {user}")
            raise HTTPException(status_code=401, detail="Unauthorized")
        return user
    else:
        if token == api_token:
            return "admin"
        logger.warning("Authentication failed: Invalid admin token")
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.delete("/images/")
@router.delete("/images")
def bulk_delete(req: BulkDeleteRequest, current_user: str = Depends(_get_token_user)):
    """
    Delete multiple images for a specific user.

    Args:
        req (BulkDeleteRequest): Request body containing user ID and list of image IDs.
        current_user (str): Authenticated user ID (or admin).

    Returns:
        dict: Summary of deleted and failed items.
    """
    logger.info(f"Bulk delete request by user: {current_user} for {len(req.image_ids)} images")
    # authorization: only allow user to delete own images, or admin
    results = {"deleted": [], "failed": []}
    for image_id in req.image_ids:
        try:
            meta = dynamodb_service.get_metadata(image_id)
            if not meta:
                results["failed"].append({"image_id": image_id, "reason": "not_found"})
                continue
            owner = meta.get('user_id')
            if current_user != 'admin' and owner != current_user:
                results["failed"].append({"image_id": image_id, "reason": "forbidden"})
                continue

            s3_key = meta.get('s3_key') or meta.get('filename') or image_id
            try:
                if s3_service.file_exists(s3_key):
                    s3_service.delete_file(s3_key)
            except Exception as e:
                logger.warning(f"Failed to delete S3 object {s3_key}: {e}")

            dynamodb_service.delete_metadata(image_id)
            results["deleted"].append(image_id)
        except Exception as e:
            results["failed"].append({"image_id": image_id, "reason": str(e)})

    return results
