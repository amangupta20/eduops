import json
import logging
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
        logger.warning(f"Scenarios directory not found at {scenarios_dir}. Returning empty list.")
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