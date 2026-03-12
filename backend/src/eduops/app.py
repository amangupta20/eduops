from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from eduops.api import api_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="eduops Core Platform")

    # Configure CORS for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allowing all origins for dev proxy compatibility
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(api_router, prefix="/api")

    # Serve static files from the 'static/' directory if it exists
    # When installed as a package, frontend/dist is included as eduops/static
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


# Module-level app instance for uvicorn
app = create_app()
