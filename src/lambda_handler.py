"""
AWS Lambda handler for the Instagram Image Service
"""
from utils.logger import get_logger
from mangum import Mangum
from main import app

logger = get_logger(__name__)
logger.info("Initializing Lambda handler")

# Create Lambda handler
handler = Mangum(app, lifespan="off")

logger.info("Lambda handler ready")
