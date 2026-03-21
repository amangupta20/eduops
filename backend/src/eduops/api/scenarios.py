from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from eduops.models.scenario import ScenarioSchema
from eduops.services.catalogue import get_scenario, list_scenarios

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


class ScenarioDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    title: str
    description: str
    difficulty: Difficulty
    tags: list[str]
    source: Source
    hints_count: int
    success_checks_count: int
    created_at: str


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


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetail)
async def get_scenario_detail(request: Request, scenario_id: str) -> ScenarioDetail:
    """Return scenario detail without exposing schema_json."""
    db_path = getattr(request.app.state, "db_path", None)
    scenario = await run_in_threadpool(get_scenario, scenario_id=scenario_id, db_path=db_path)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    try:
        parsed_schema = ScenarioSchema.model_validate_json(scenario["schema_json"])
    except Exception as exc:  # pragma: no cover - defensive path for corrupted rows
        raise HTTPException(status_code=500, detail="Stored scenario schema is invalid") from exc

    return ScenarioDetail(
        id=scenario["id"],
        title=scenario["title"],
        description=scenario["description"],
        difficulty=scenario["difficulty"],
        tags=scenario["tags"],
        source=scenario["source"],
        hints_count=len(parsed_schema.hints),
        success_checks_count=len(parsed_schema.success_checks),
        created_at=scenario["created_at"],
    )
