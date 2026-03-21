from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.concurrency import run_in_threadpool

from eduops.models.scenario import ScenarioSchema
from eduops.services.catalogue import get_scenario, list_scenarios

router = APIRouter()

Difficulty = Literal["easy", "medium", "hard"]
Source = Literal["bundled", "generated"]


def _to_rfc3339_utc_z(value: str) -> str:
    """Normalize aware UTC timestamps to RFC3339 Z form."""
    if value.endswith("Z"):
        return value
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        return value
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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

    normalized_scenarios = [
        {**scenario, "created_at": _to_rfc3339_utc_z(scenario["created_at"])}
        for scenario in scenarios
    ]

    return ScenarioListResponse(
        scenarios=[
            ScenarioSummary.model_validate(scenario) for scenario in normalized_scenarios
        ]
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
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=500, detail="Invalid scenario schema") from exc

    return ScenarioDetail(
        id=scenario["id"],
        title=scenario["title"],
        description=scenario["description"],
        difficulty=scenario["difficulty"],
        tags=scenario["tags"],
        source=scenario["source"],
        hints_count=len(parsed_schema.hints),
        success_checks_count=len(parsed_schema.success_checks),
        created_at=_to_rfc3339_utc_z(scenario["created_at"]),
    )
