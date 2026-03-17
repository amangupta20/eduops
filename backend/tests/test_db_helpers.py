"""Tests for SQLite query helpers in eduops.db."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from eduops.db import execute, fetchall, fetchone, get_db, init_db


def test_get_db_sets_row_factory(db_path: Path) -> None:
    """Connections from get_db should return rows addressable by column name."""
    init_db(db_path)

    with get_db(db_path) as conn:
        row = fetchone(conn, "SELECT 1 AS value")

    assert row is not None
    assert isinstance(row, sqlite3.Row)
    assert row["value"] == 1


def test_execute_and_fetch_wrappers_are_parameterized(db_path: Path) -> None:
    """Wrapper helpers should safely bind user input values via SQL parameters."""
    init_db(db_path)

    scenario_id = "s1"
    title = "safe-title"
    description = "desc"
    difficulty = "easy"
    tags = '[]'
    source = "bundled"
    schema_json = "{}"
    # Contains SQL-looking text that would be dangerous if interpolated.
    created_at = "2026-03-17'); DROP TABLE scenarios; --"

    insert_sql = (
        "INSERT INTO scenarios "
        "(id, title, description, difficulty, tags, source, schema_json, embedding, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    with get_db(db_path) as conn:
        execute(
            conn,
            insert_sql,
            (
                scenario_id,
                title,
                description,
                difficulty,
                tags,
                source,
                schema_json,
                b"\x00" * 1536,
                created_at,
            ),
        )

        row = fetchone(conn, "SELECT id, created_at FROM scenarios WHERE id = ?", (scenario_id,))
        rows = fetchall(conn, "SELECT id FROM scenarios WHERE source = ?", (source,))

    assert row is not None
    assert row["id"] == scenario_id
    assert row["created_at"] == created_at
    assert len(rows) == 1
    assert rows[0]["id"] == scenario_id
