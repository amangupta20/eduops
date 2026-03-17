from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from eduops.api import api_router

from contextlib import asynccontextmanager
import logging

# Note: You may need to adjust this import path depending on where T012 put init_db
from eduops.db import init_db

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP HOOK ---
    logger.info("Initializing EduOps database...")
    init_db()
    
    # The server runs while paused at this yield statement
    yield  
    
    # --- SHUTDOWN HOOK ---
    logger.info("Shutting down EduOps platform. Running cleanup...")
    # Placeholder for future teardown logic (e.g., stopping orphaned Docker containers)
    pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="eduops Core Platform",lifespan=lifespan)

    # Configure CORS for development — allow all origins (no credentials needed;
    # the Vite dev proxy forwards /api requests, so cookies/auth headers are not
    # used across origins during development)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(api_router, prefix="/api")

    # Serve static files from the 'static/' directory if it exists.
    # In packaged installs, the built frontend (frontend/dist) is expected
    # to be placed here by the packaging configuration (see T097).
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


# Module-level app instance for uvicorn
app = create_app()
