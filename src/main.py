from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from api.routes import images, health
from utils.logger import get_logger
import time

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 {settings.app_name} started - Environment: {settings.environment}")
    yield
    logger.info(f"🛑 {settings.app_name} shutting down")

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    description="Instagram-like image service with S3 and DynamoDB",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(time.time())
    auth = request.headers.get("authorization")
    user = None
    if auth and auth.startswith("Bearer "):
        try:
            token = auth.split(" ", 1)[1]
            if ":" in token:
                user = token.split(":", 1)[0]
        except Exception:
            user = None

    client_host = None
    try:
        client_host = request.client.host if request.client else None
    except Exception:
        client_host = None

    extras_base = {
        'request_id': request_id,
        'method': request.method,
        'path': request.url.path,
        'client': client_host,
        'auth_present': bool(auth),
        'user': user,
    }

    logger.info("request_start", extra={**extras_base})

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    extras_end = {**extras_base, 'status_code': response.status_code, 'duration_ms': int(duration * 1000)}
    logger.info("request_completed", extra={**extras_end})
    return response

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(images.router, prefix="/api/v1", tags=["Images"])


@app.get("/")
def root():
    return {
        "service": settings.app_name,
        "environment": settings.environment,
        "version": "1.0.0"
    }
