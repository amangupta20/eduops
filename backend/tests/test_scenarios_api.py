"""Tests for GET /api/scenarios endpoint."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from eduops.api import scenarios as scenarios_api


def _scenario_summary(scenario_id: str, difficulty: str, source: str) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "title": f"Scenario {scenario_id}",
        "description": "Practice Docker basics",
        "difficulty": difficulty,
        "tags": ["docker", "practice"],
        "source": source,
        "created_at": "2026-03-19T12:00:00Z",
    }


@pytest.mark.asyncio
async def test_get_scenarios_returns_contract_shape(
    async_client: AsyncClient,
    monkeypatch: Any,
) -> None:
    """Endpoint should return scenario summaries under the 'scenarios' key."""

    def fake_list_scenarios(
        difficulty: str | None = None,
        source: str | None = None,
        db_path: Any = None,
    ) -> list[dict[str, Any]]:
        assert difficulty is None
        assert source is None
        assert db_path is None
        return [_scenario_summary("s1", "easy", "bundled")]

    monkeypatch.setattr(scenarios_api, "list_scenarios", fake_list_scenarios)

    response = await async_client.get("/api/scenarios")

    assert response.status_code == 200
    payload = response.json()
    assert "scenarios" in payload
    assert len(payload["scenarios"]) == 1
    assert payload["scenarios"][0]["id"] == "s1"
    assert "schema_json" not in payload["scenarios"][0]


@pytest.mark.asyncio
async def test_get_scenarios_forwards_optional_filters(
    async_client: AsyncClient,
    monkeypatch: Any,
) -> None:
    """difficulty and source query params should be forwarded to service layer."""
    captured: dict[str, Any] = {}

    def fake_list_scenarios(
        difficulty: str | None = None,
        source: str | None = None,
        db_path: Any = None,
    ) -> list[dict[str, Any]]:
        captured["difficulty"] = difficulty
        captured["source"] = source
        captured["db_path"] = db_path
        return [_scenario_summary("s2", "hard", "generated")]

    monkeypatch.setattr(scenarios_api, "list_scenarios", fake_list_scenarios)

    response = await async_client.get("/api/scenarios?difficulty=hard&source=generated")

    assert response.status_code == 200
    assert captured == {"difficulty": "hard", "source": "generated", "db_path": None}
    payload = response.json()
    assert payload["scenarios"][0]["difficulty"] == "hard"
    assert payload["scenarios"][0]["source"] == "generated"
