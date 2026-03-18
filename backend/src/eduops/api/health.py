from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter()

# Define the exact shape required by the API contract
class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    
    docker_status: str
    llm_configured: bool
    active_session_id: str | None
    scenario_count: int

@router.get("/health", response_model=HealthResponse)
async def check_health() -> HealthResponse:
    """
    Get the health status of the EduOps backend dependencies.
    """
    # Placeholder values: These will be wired up to actual system checks in future tasks
    return HealthResponse(
        docker_status="connected",
        llm_configured=True,
        active_session_id=None,
        scenario_count=0
    )