"""FastAPI application for rag-eval API.

Provides REST API endpoints for:
- Target management
- Benchmark management
- Metric configuration
- Test definitions
- Evaluation runs
- Results and reporting
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag_eval.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting rag-eval API")
    settings = get_settings()
    logger.info("Database URL: %s", settings.database_url.replace("://", "://***@"))

    yield

    # Shutdown
    logger.info("Shutting down rag-eval API")


# Create FastAPI application
app = FastAPI(
    title="rag-eval API",
    description="API for RAG evaluation management and execution",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
allowed_origins = (
    settings.cors_origins.split(",")
    if settings.cors_origins
    else ["http://localhost:3000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions.

    Args:
        request: HTTP request.
        exc: Exception that was raised.

    Returns:
        JSON error response.
    """
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint.

    Returns:
        Health status.
    """
    return {
        "status": "healthy",
        "service": "rag-eval-api",
        "version": "0.1.0",
    }


# Import and include routers
# These will be created in subsequent files
# from rag_eval.api import targets, benchmarks, metric_configs, test_definitions, runs

# app.include_router(targets.router, prefix="/api/v1", tags=["targets"])
# app.include_router(benchmarks.router, prefix="/api/v1", tags=["benchmarks"])
# app.include_router(
#     metric_configs.router, prefix="/api/v1", tags=["metric-configs"]
# )
# app.include_router(
#     test_definitions.router, prefix="/api/v1", tags=["test-definitions"]
# )
# app.include_router(runs.router, prefix="/api/v1", tags=["runs"])


# Root endpoint
@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint with API information.

    Returns:
        API information.
    """
    return {
        "name": "rag-eval API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
