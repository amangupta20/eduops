import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from eduops.api import api_router
# NOTE: Verify this import matches where your init_db function was created in T012!
from eduops.db import init_db 

logger = logging.getLogger(__name__)

def create_app(db_path: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Initializing EduOps database...")
        # We pass the db_path to init_db to prevent side effects in testing
        init_db(db_path)
        
        yield
        
        logger.info("Shutting down EduOps platform. Running cleanup...")
        # Placeholder hook for cleanup
        pass

    # We attach the lifespan manager right when we create the FastAPI instance
    app = FastAPI(title="eduops Core Platform", lifespan=lifespan)
    app.state.db_path = db_path

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