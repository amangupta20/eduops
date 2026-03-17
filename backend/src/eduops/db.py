"""
backend/src/eduops/db.py

SQLite schema DDL and database initialisation.

Constitution constraint: no ORM — raw sqlite3 only.
Schema defined in specs/001-core-platform/data-model.md.
"""

import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

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

_SQLParams = Sequence[Any] | Mapping[str, Any]


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign-key enforcement enabled.

    SQLite does not enforce REFERENCES constraints unless
    ``PRAGMA foreign_keys = ON`` is set for every connection.  This
    helper ensures that constraint is always active.

    Args:
        db_path: Absolute, resolved path to the database file.

    Returns:
        An open ``sqlite3.Connection`` with foreign keys enabled.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection configured for keyed row access.

    This context manager wraps work in a transaction-like lifecycle:
    commit on normal exit and rollback if an exception escapes.

    Args:
        path: Optional database path. Uses ``~/.eduops/eduops.db`` when omitted.

    Yields:
        Open ``sqlite3.Connection`` configured with ``sqlite3.Row`` row factory.
    """
    db_path = Path(path or _DEFAULT_DB_PATH).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(
    conn: sqlite3.Connection,
    query: str,
    params: _SQLParams = (),
    commit: bool = False,
) -> sqlite3.Cursor:
    """Execute a parameterised write/query statement.

    ``params`` are always bound via sqlite placeholders (``?`` / named params),
    preventing string interpolation in SQL execution paths.

    Args:
        conn: Active SQLite connection.
        query: SQL statement with placeholders.
        params: Positional or named parameters to bind.
        commit: When ``True``, commit immediately after execution.
            Defaults to ``False`` so transaction contexts can control commit.
    """
    cur = conn.execute(query, params)
    if commit:
        conn.commit()
    return cur


def fetchone(conn: sqlite3.Connection, query: str, params: _SQLParams = ()) -> sqlite3.Row | None:
    """Execute a parameterised SELECT and return a single row."""
    return conn.execute(query, params).fetchone()


def fetchall(conn: sqlite3.Connection, query: str, params: _SQLParams = ()) -> list[sqlite3.Row]:
    """Execute a parameterised SELECT and return all rows."""
    return conn.execute(query, params).fetchall()


def init_db(path: Path | None = None) -> None:
    """Create all four tables and their indexes if they do not already exist.

    Idempotent — safe to call on every startup.

    Args:
        path: Path to the SQLite database file.  ``~`` is expanded and the
              result is resolved to an absolute path.  Defaults to
              ``~/.eduops/eduops.db``.  Parent directories are created
              automatically.
    """
    db_path = Path(path or _DEFAULT_DB_PATH).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = _connect(db_path)
    try:
        conn.executescript(_DDL)
        conn.commit()
    finally:
        conn.close()
