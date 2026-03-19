from fastapi import APIRouter
from eduops.api.health import router as health_router
from eduops.api.scenarios import router as scenarios_router

api_router = APIRouter()

# Mount the health router
api_router.include_router(health_router, tags=["health"])
api_router.include_router(scenarios_router, tags=["scenarios"])