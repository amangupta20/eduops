import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from eduops.db import fetchall, fetchone, get_db
from eduops.models.scenario import ScenarioSchema

logger = logging.getLogger(__name__)


def _normalize_utc_timestamp(value: str) -> str:
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


def get_scenarios_dir() -> Path:
    """Resolve the absolute path to the bundled scenarios directory."""
    return Path(__file__).resolve().parent.parent / "scenarios"


def load_bundled_scenarios() -> list[ScenarioSchema]:
    """
    Read all JSON files from the scenarios directory, parse them into ScenarioSchema,
    and return the list of valid scenarios. Handles empty or missing directories gracefully.
    """
    scenarios_dir = get_scenarios_dir()
    scenarios: list[ScenarioSchema] = []

    # Gracefully handle the case where the directory doesn't exist yet
    if not scenarios_dir.exists() or not scenarios_dir.is_dir():
        logger.warning(
            f"Scenarios directory not found at {scenarios_dir}. Returning empty list."
        )
        return scenarios

    # Iterate through all JSON files in the directory
    for filepath in scenarios_dir.glob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse the raw dictionary into our strict Pydantic model
            scenario = ScenarioSchema.model_validate(data)
            scenarios.append(scenario)
            logger.debug(f"Successfully loaded scenario: {filepath.name}")

        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse invalid JSON in {filepath.name}: {e}")
        except ValidationError as e:
            logger.error(f"Schema validation failed for {filepath.name}: {e}")
        except OSError as e:
            logger.error(f"Failed to read {filepath.name}: {e}")

    logger.info(f"Loaded {len(scenarios)} bundled scenarios from {scenarios_dir}")
    return scenarios


def upsert_scenario(
    conn: sqlite3.Connection,
    scenario: ScenarioSchema,
    embedding: bytes,
    source: str,
    title: str,
    difficulty: str,
    tags: list[str],
    created_at: str | None = None,
) -> None:
    """
    Insert or update a scenario row in the DB by ID.

    Uses ``INSERT OR REPLACE INTO`` so the call is idempotent: calling it
    again with the same ``scenario.id`` will overwrite the existing row,
    which is the desired behaviour for bundled scenario startup upserts and
    for updating a generated scenario's embedding.

    Args:
        conn:       Active SQLite connection (caller controls the transaction).
        scenario:   Validated ScenarioSchema to persist.
        embedding:  Pre-computed 384-dim float32 vector serialised as bytes
                    (1536 bytes).  Stored directly as a BLOB.
        source:     Origin of the scenario — ``'bundled'`` or ``'generated'``.
        title:      Human-readable scenario title (maps to ``scenarios.title``).
        difficulty: One of ``'easy'``, ``'medium'``, or ``'hard'``.
        tags:       List of tag strings; serialised as a JSON array for storage.
        created_at: ISO 8601 timestamp string.  Defaults to the current UTC
                    time when omitted.
    """
    if source not in ("bundled", "generated"):
        raise ValueError(f"source must be 'bundled' or 'generated', got {source!r}")
    if difficulty not in ("easy", "medium", "hard"):
        raise ValueError(
            f"difficulty must be 'easy', 'medium', or 'hard', got {difficulty!r}"
        )
    if len(embedding) != 1536:
        raise ValueError(f"embedding must be exactly 1536 bytes, got {len(embedding)}")

    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        created_at = _normalize_utc_timestamp(created_at)

    schema_json: str = scenario.model_dump_json()
    tags_json: str = json.dumps(tags)

    conn.execute(
        """
        INSERT INTO scenarios
            (id, title, description, difficulty, tags, source, schema_json, embedding, created_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            difficulty = excluded.difficulty,
            tags = excluded.tags,
            source = excluded.source,
            schema_json = excluded.schema_json,
            embedding = excluded.embedding
        """,
        (
            scenario.id,
            title,
            scenario.description,
            difficulty,
            tags_json,
            source,
            schema_json,
            embedding,
            created_at,
        ),
    )
    logger.debug("Upserted scenario id=%s source=%s", scenario.id, source)


def _parse_tags(raw_tags: str) -> list[str]:
    """Convert persisted JSON tags into a list of strings."""
    try:
        value = json.loads(raw_tags)
        if isinstance(value, list) and all(isinstance(tag, str) for tag in value):
            return value
        logger.warning(
            "Scenario tags JSON has unexpected structure; expected list[str], got %r. "
            "Returning empty tag list.",
            value,
        )
    except json.JSONDecodeError as exc:
        logger.warning(
            "Failed to parse scenario tags JSON; returning empty tag list. Error: %s",
            exc,
            exc_info=True,
        )
    return []


def list_scenarios(
    difficulty: str | None = None,
    source: str | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return scenario summaries, optionally filtered by difficulty and source."""
    query = (
        "SELECT id, title, description, difficulty, tags, source, created_at "
        "FROM scenarios"
    )
    where_clauses: list[str] = []
    params: list[Any] = []

    if difficulty is not None:
        where_clauses.append("difficulty = ?")
        params.append(difficulty)

    if source is not None:
        where_clauses.append("source = ?")
        params.append(source)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY created_at DESC"

    with get_db(db_path) as conn:
        rows = fetchall(conn, query, tuple(params))

    # Summary response intentionally excludes schema_json and embedding.
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "difficulty": row["difficulty"],
            "tags": _parse_tags(row["tags"]),
            "source": row["source"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_scenario(scenario_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Return a full scenario record by id, or None if not found."""
    query = (
        "SELECT id, title, description, difficulty, tags, source, schema_json, embedding, created_at "
        "FROM scenarios WHERE id = ?"
    )

    with get_db(db_path) as conn:
        row = fetchone(conn, query, (scenario_id,))

    if row is None:
        return None

    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "difficulty": row["difficulty"],
        "tags": _parse_tags(row["tags"]),
        "source": row["source"],
        "schema_json": row["schema_json"],
        "embedding": row["embedding"],
        "created_at": row["created_at"],
    }
