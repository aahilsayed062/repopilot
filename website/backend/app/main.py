"""
RepoPilot Website — FastAPI Application Entry Point

Lightweight API for GitHub repo architecture analysis.
Paste a GitHub URL → clone → analyze → return interactive architecture overview.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from dotenv import load_dotenv
load_dotenv()
from app.utils.logger import setup_logging, get_logger, set_request_id
from app.routes import health, analyze


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    setup_logging(debug=settings.debug)
    logger = get_logger("main")
    
    llm_provider = "Gemini" if settings.gemini_api_key else "Mock (no GEMINI_API_KEY)"
    
    logger.info(
        "starting_repopilot_website",
        version=settings.app_version,
        llm_provider=llm_provider,
    )
    
    yield
    
    logger.info("shutting_down_repopilot_website")


# Create FastAPI app
app = FastAPI(
    title="RepoPilot Website API",
    version=settings.app_version,
    description="GitHub repo architecture analysis API — paste a URL, get an interactive overview",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Add request_id to each request for tracing."""
    # Check for existing request ID in headers or generate new one
    request_id = request.headers.get("X-Request-ID")
    set_request_id(request_id)
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = set_request_id()
    return response


# Register routers
app.include_router(health.router)
app.include_router(analyze.router)


from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure JSON response."""
    # Log the full error
    import traceback
    error_details = traceback.format_exc()
    logger = get_logger("main")
    logger.error("unhandled_exception", error=str(exc), traceback=error_details)
    
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"},
    )


# Root redirect to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API docs."""
    return {"message": "Welcome to RepoPilot Website API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
