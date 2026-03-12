"""Shared pytest fixtures for eduops backend tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import AsyncGenerator, Iterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

# DDL mirrors data-model.md — four tables, all indexes.
_SCHEMA_DDL = """\
CREATE TABLE IF NOT EXISTS scenarios (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    difficulty  TEXT NOT NULL CHECK(difficulty IN ('easy','medium','hard')),
    tags        TEXT NOT NULL,
    source      TEXT NOT NULL CHECK(source IN ('bundled','generated')),
    schema_json TEXT NOT NULL,
    embedding   BLOB NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scenarios_source     ON scenarios(source);
CREATE INDEX IF NOT EXISTS idx_scenarios_difficulty  ON scenarios(difficulty);

CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    scenario_id    TEXT NOT NULL REFERENCES scenarios(id),
    status         TEXT NOT NULL CHECK(status IN ('active','completed','abandoned')),
    workspace_path TEXT NOT NULL,
    started_at     TEXT NOT NULL,
    completed_at   TEXT,
    review_text    TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_status      ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_scenario_id ON sessions(scenario_id);

CREATE TABLE IF NOT EXISTS hint_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL REFERENCES sessions(id),
    hint_index  INTEGER NOT NULL,
    shown_at    TEXT    NOT NULL,
    UNIQUE(session_id, hint_index)
);

CREATE TABLE IF NOT EXISTS chat_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a fresh temporary SQLite database path (file does not yet exist).

    Each test receives its own isolated path under pytest's ``tmp_path``.
    """
    return tmp_path / "test_eduops.db"


@pytest.fixture()
def db_conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Return an initialised SQLite connection with the full eduops schema.

    The connection uses ``sqlite3.Row`` as ``row_factory`` so rows can be
    accessed by column name.  The database is created in a per-test temp
    directory and is automatically cleaned up by pytest.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_DDL)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# FastAPI / httpx async client fixture
# ---------------------------------------------------------------------------


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app for testing.

    Once ``eduops.app.create_app`` exists (T018), this helper should be
    replaced with an import of that factory — the fixture below will keep
    the same interface.  For now we return a bare app so the fixture is
    usable as soon as any API router is ready to be mounted.
    """
    try:
        from eduops.app import create_app
    except ImportError:
        return FastAPI(title="eduops-test")

    return create_app()


@pytest_asyncio.fixture()
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Yield an ``httpx.AsyncClient`` wired to the test FastAPI app.

    Uses httpx's ``ASGITransport`` so no real server is started.
    The base URL is set to ``http://test`` by convention.
    """
    from httpx import ASGITransport

    app = _create_test_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
