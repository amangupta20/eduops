"""Tests for GET /api/scenarios endpoint."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx import ASGITransport

from eduops.api import scenarios as scenarios_api
from eduops.app import create_app


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
    scenarios_api_client: tuple[AsyncClient, Path],
    monkeypatch: Any,
) -> None:
    """Endpoint should return scenario summaries under the 'scenarios' key."""
    async_client, expected_db_path = scenarios_api_client

    def fake_list_scenarios(
        difficulty: str | None = None,
        source: str | None = None,
        db_path: Any = None,
    ) -> list[dict[str, Any]]:
        assert difficulty is None
        assert source is None
        assert db_path == expected_db_path
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
    scenarios_api_client: tuple[AsyncClient, Path],
    monkeypatch: Any,
) -> None:
    """difficulty and source query params should be forwarded to service layer."""
    async_client, expected_db_path = scenarios_api_client
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
    assert captured == {
        "difficulty": "hard",
        "source": "generated",
        "db_path": expected_db_path,
    }
    payload = response.json()
    assert payload["scenarios"][0]["difficulty"] == "hard"
    assert payload["scenarios"][0]["source"] == "generated"


@pytest_asyncio.fixture()
async def scenarios_api_client(tmp_path: Path) -> AsyncGenerator[tuple[AsyncClient, Path], None]:
    """Create a per-test app/client using an isolated temporary SQLite file."""
    db_path = tmp_path / "scenarios_api_test.db"
    app = create_app(db_path=db_path)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, db_path
