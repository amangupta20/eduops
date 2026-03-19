from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from eduops.services.catalogue import list_scenarios

router = APIRouter()

Difficulty = Literal["easy", "medium", "hard"]
Source = Literal["bundled", "generated"]


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    title: str
    description: str
    difficulty: Difficulty
    tags: list[str]
    source: Source
    created_at: str


class ScenarioListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    scenarios: list[ScenarioSummary]


@router.get("/scenarios", response_model=ScenarioListResponse)
async def get_scenarios(
    request: Request,
    difficulty: Difficulty | None = Query(default=None),
    source: Source | None = Query(default=None),
) -> ScenarioListResponse:
    """Return scenario summaries, optionally filtered by difficulty and source."""
    db_path = getattr(request.app.state, "db_path", None)
    scenarios = await run_in_threadpool(
        list_scenarios,
        difficulty=difficulty,
        source=source,
        db_path=db_path,
    )
    return ScenarioListResponse(
        scenarios=[ScenarioSummary.model_validate(scenario) for scenario in scenarios]
    )
