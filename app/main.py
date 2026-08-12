import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.metrics import HTTP_REQUEST_DURATION_SECONDS
from app.db.mongodb import close_mongo_connection, connect_to_mongo
from app.services.llm_service import LLMServiceError

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifespan events."""
    logger.info("Initializing %s v%s...", settings.PROJECT_NAME, settings.VERSION)
    await connect_to_mongo()
    yield
    await close_mongo_connection()
    logger.info("Application shutdown completed.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.middleware("http")
async def record_request_metrics(request: Request, call_next):
    """Middleware measuring request processing duration for Prometheus."""
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time
    endpoint = request.url.path
    HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, endpoint=endpoint).observe(duration)
    return response


@app.get("/metrics")
async def get_prometheus_metrics():
    """Expose Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(LLMServiceError)
async def llm_exception_handler(request: Request, exc: LLMServiceError):
    logger.error("LLM Exception caught: %s", str(exc))
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"LLM Service Error: {str(exc)}"},
    )


# Register API Router
app.include_router(api_router)

# Base static dir path
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Explicit file routes for maximum compatibility
@app.get("/styles.css")
async def serve_styles_direct():
    return FileResponse(os.path.join(STATIC_DIR, "styles.css"), media_type="text/css")


@app.get("/app.js")
async def serve_js_direct():
    return FileResponse(os.path.join(STATIC_DIR, "app.js"), media_type="text/javascript")


# Mount /static directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse)
async def serve_index():
    """Serve index.html at root route."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
