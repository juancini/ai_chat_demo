import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
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


@app.exception_handler(LLMServiceError)
async def llm_exception_handler(request: Request, exc: LLMServiceError):
    logger.error("LLM Exception caught: %s", str(exc))
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"LLM Service Error: {str(exc)}"},
    )


# Register API Router
app.include_router(api_router)

# Mount static files under /static
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=FileResponse)
async def serve_index():
    """Serve index.html at root route."""
    return FileResponse("app/static/index.html")
