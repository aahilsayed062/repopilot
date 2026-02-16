"""
TaskFlow API - Main application entry point.

A lightweight task management REST API with JWT authentication.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routes import auth_router, task_router

# Create application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="A task management API with JWT authentication and SQLAlchemy ORM.",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(task_router)


@app.on_event("startup")
def on_startup():
    """Initialize database tables on startup."""
    init_db()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.VERSION}
