"""
backend/src/eduops/db.py

SQLite schema DDL and database initialisation.

Constitution constraint: no ORM — raw sqlite3 only.
Schema defined in specs/001-core-platform/data-model.md.
"""

import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_DDL = """\
CREATE TABLE IF NOT EXISTS scenarios (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    difficulty  TEXT NOT NULL CHECK(difficulty IN ('easy', 'medium', 'hard')),
    tags        TEXT NOT NULL,
    source      TEXT NOT NULL CHECK(source IN ('bundled', 'generated')),
    schema_json TEXT NOT NULL,
    embedding   BLOB NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scenarios_source     ON scenarios(source);
CREATE INDEX IF NOT EXISTS idx_scenarios_difficulty ON scenarios(difficulty);

CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    scenario_id    TEXT NOT NULL REFERENCES scenarios(id),
    status         TEXT NOT NULL CHECK(status IN ('active', 'completed', 'abandoned')),
    workspace_path TEXT NOT NULL,
    started_at     TEXT NOT NULL,
    completed_at   TEXT,
    review_text    TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_status      ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_scenario_id ON sessions(scenario_id);

CREATE TABLE IF NOT EXISTS hint_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT    NOT NULL REFERENCES sessions(id),
    hint_index INTEGER NOT NULL,
    shown_at   TEXT    NOT NULL,
    UNIQUE(session_id, hint_index)
);

CREATE TABLE IF NOT EXISTS chat_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_log_session      ON chat_log(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_log_session_time ON chat_log(session_id, created_at);
"""

# Default database path: ~/.eduops/eduops.db
_DEFAULT_DB_PATH = Path.home() / ".eduops" / "eduops.db"


def init_db(path: Path | None = None) -> None:
    """Create all four tables and their indexes if they do not already exist.

    Idempotent — safe to call on every startup.

    Args:
        path: Absolute path to the SQLite database file.  Defaults to
              ``~/.eduops/eduops.db``.  Parent directories are created
              automatically.
    """
    db_path = path or _DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_DDL)
        conn.commit()
    finally:
        conn.close()
