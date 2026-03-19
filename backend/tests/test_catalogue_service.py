"""Tests for scenario listing and retrieval in eduops.services.catalogue."""

from __future__ import annotations

import json
from pathlib import Path

from eduops.db import execute, get_db, init_db
from eduops.services.catalogue import get_scenario, list_scenarios


def _insert_scenario(
    db_path: Path,
    *,
    scenario_id: str,
    title: str,
    description: str,
    difficulty: str,
    tags: list[str],
    source: str,
    schema_json: str,
    created_at: str,
) -> None:
    with get_db(db_path) as conn:
        execute(
            conn,
            (
                "INSERT INTO scenarios "
                "(id, title, description, difficulty, tags, source, schema_json, embedding, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                scenario_id,
                title,
                description,
                difficulty,
                json.dumps(tags),
                source,
                schema_json,
                b"\x00" * 1536,
                created_at,
            ),
            commit=True,
        )


def test_list_scenarios_returns_summaries_without_schema_json(db_path: Path) -> None:
    """list_scenarios should return summary fields only and parse tags."""
    init_db(db_path)
    _insert_scenario(
        db_path,
        scenario_id="s1",
        title="List Containers",
        description="Use docker ps",
        difficulty="easy",
        tags=["docker", "containers"],
        source="bundled",
        schema_json='{"hidden": true}',
        created_at="2026-03-19T10:00:00Z",
    )

    scenarios = list_scenarios(db_path=db_path)

    assert len(scenarios) == 1
    assert scenarios[0]["id"] == "s1"
    assert scenarios[0]["tags"] == ["docker", "containers"]
    assert "schema_json" not in scenarios[0]
    assert "embedding" not in scenarios[0]


def test_list_scenarios_applies_optional_difficulty_and_source_filters(db_path: Path) -> None:
    """list_scenarios should support independent and combined optional filters."""
    init_db(db_path)
    _insert_scenario(
        db_path,
        scenario_id="s1",
        title="Easy Bundled",
        description="d1",
        difficulty="easy",
        tags=["a"],
        source="bundled",
        schema_json="{}",
        created_at="2026-03-19T10:00:00Z",
    )
    _insert_scenario(
        db_path,
        scenario_id="s2",
        title="Hard Generated",
        description="d2",
        difficulty="hard",
        tags=["b"],
        source="generated",
        schema_json="{}",
        created_at="2026-03-19T11:00:00Z",
    )
    _insert_scenario(
        db_path,
        scenario_id="s3",
        title="Hard Bundled",
        description="d3",
        difficulty="hard",
        tags=["c"],
        source="bundled",
        schema_json="{}",
        created_at="2026-03-19T12:00:00Z",
    )

    hard_only = list_scenarios(difficulty="hard", db_path=db_path)
    bundled_only = list_scenarios(source="bundled", db_path=db_path)
    hard_bundled = list_scenarios(difficulty="hard", source="bundled", db_path=db_path)

    assert {scenario["id"] for scenario in hard_only} == {"s2", "s3"}
    assert {scenario["id"] for scenario in bundled_only} == {"s1", "s3"}
    assert [scenario["id"] for scenario in hard_bundled] == ["s3"]


def test_get_scenario_returns_full_record_or_none(db_path: Path) -> None:
    """get_scenario should return full stored fields or None for unknown IDs."""
    init_db(db_path)
    _insert_scenario(
        db_path,
        scenario_id="s1",
        title="Inspect Image",
        description="Use docker image inspect",
        difficulty="medium",
        tags=["images"],
        source="generated",
        schema_json='{"checks": [1, 2]}',
        created_at="2026-03-19T13:00:00Z",
    )

    found = get_scenario("s1", db_path=db_path)
    missing = get_scenario("does-not-exist", db_path=db_path)

    assert found is not None
    assert found["id"] == "s1"
    assert found["title"] == "Inspect Image"
    assert found["tags"] == ["images"]
    assert found["schema_json"] == '{"checks": [1, 2]}'
    assert isinstance(found["embedding"], bytes)
    assert missing is None


def test_list_and_get_are_safe_with_sql_like_input_values(db_path: Path) -> None:
    """Inputs must be bound as SQL params, not interpolated into queries."""
    init_db(db_path)
    _insert_scenario(
        db_path,
        scenario_id="safe-id",
        title="Safe",
        description="Safe",
        difficulty="easy",
        tags=["safe"],
        source="bundled",
        schema_json="{}",
        created_at="2026-03-19T14:00:00Z",
    )

    injected_filter = "bundled' OR 1=1 --"
    injected_id = "safe-id' OR 1=1 --"

    assert list_scenarios(source=injected_filter, db_path=db_path) == []
    assert get_scenario(injected_id, db_path=db_path) is None
    assert get_scenario("safe-id", db_path=db_path) is not None
