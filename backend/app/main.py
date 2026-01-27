"""
RepoPilot AI - FastAPI Application Entry Point

A repository-grounded engineering assistant that provides answers,
generates code, and writes tests only when supported by evidence.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
# Force explicit env load check
from dotenv import load_dotenv
load_dotenv()
from app.utils.logger import setup_logging, get_logger, set_request_id
from app.routes import health, repo, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    setup_logging(debug=settings.debug)
    logger = get_logger("main")
    
    # Determine providers for logging
    embedding_provider = "Gemini" if settings.gemini_api_key else ("OpenAI" if settings.openai_api_key else "Mock")
    chat_provider = "Groq" if (settings.openai_api_key and settings.openai_base_url and "groq" in settings.openai_base_url) else ("Gemini" if settings.gemini_api_key else "Mock")
    
    logger.info(
        "starting_repopilot",
        version=settings.app_version,
        embedding_provider=embedding_provider,
        chat_provider=chat_provider,
        data_dir=str(settings.data_dir)
    )
    
    # Ensure data directory exists
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("shutting_down_repopilot")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Repository-grounded engineering assistant",
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
app.include_router(repo.router)
app.include_router(chat.router)


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
    return {"message": "Welcome to RepoPilot AI", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
