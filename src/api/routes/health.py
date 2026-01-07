"""
Health check route for the service.
Provides an endpoint to verify the service status and environment.
"""
from fastapi import APIRouter
from config import settings

router = APIRouter()

@router.get("/health")
def health_check():
    """
    Perform a basic health check.

    Returns:
        dict: Status information including environment and service name.
    """
    return {
        "status": "healthy",
        "environment": settings.environment,
        "service": settings.app_name
    }
