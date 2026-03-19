import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from eduops.models.scenario import ScenarioSchema

logger = logging.getLogger(__name__)


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

    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()

    schema_json: str = scenario.model_dump_json()
    tags_json: str = json.dumps(tags)

    conn.execute(
        """
        INSERT OR REPLACE INTO scenarios
            (id, title, description, difficulty, tags, source, schema_json, embedding, created_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
