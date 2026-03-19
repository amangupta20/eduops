import sqlite3
import pytest
from eduops.models.scenario import ScenarioSchema, ScenarioSummary
from eduops.services.catalogue import upsert_scenario, list_scenarios, get_scenario

@pytest.fixture
def sample_scenario() -> ScenarioSchema:
    return ScenarioSchema(
        id="test-scenario-1",
        name="Test Scenario 1",
        description="A test scenario",
        setup_actions=[],
        success_checks=[],
        expected_containers=["web"],
        hints=["Hint 1"],
        workspace_files=[]
    )

def test_upsert_and_get_scenario(db_conn: sqlite3.Connection, sample_scenario: ScenarioSchema):
    # Prepare data
    embedding = b"\x00" * 1536
    
    # Upsert
    upsert_scenario(
        conn=db_conn,
        scenario=sample_scenario,
        embedding=embedding,
        source="bundled",
        title=sample_scenario.name,
        difficulty="easy",
        tags=["docker", "test"]
    )
    
    # Get
    retrieved = get_scenario(db_conn, sample_scenario.id)
    
    assert retrieved is not None
    assert retrieved.id == sample_scenario.id
    assert retrieved.name == sample_scenario.name
    assert retrieved.description == sample_scenario.description
    assert retrieved.expected_containers == ["web"]

def test_get_scenario_not_found(db_conn: sqlite3.Connection):
    assert get_scenario(db_conn, "non-existent") is None

def test_list_scenarios_filtering(db_conn: sqlite3.Connection, sample_scenario: ScenarioSchema):
    embedding = b"\x00" * 1536
    
    # Insert two scenarios
    upsert_scenario(
        conn=db_conn,
        scenario=sample_scenario,
        embedding=embedding,
        source="bundled",
        title="Scenario 1",
        difficulty="easy",
        tags=["tag1"]
    )
    
    scenario2 = sample_scenario.model_copy(update={"id": "test-scenario-2"})
    upsert_scenario(
        conn=db_conn,
        scenario=scenario2,
        embedding=embedding,
        source="generated",
        title="Scenario 2",
        difficulty="hard",
        tags=["tag2"]
    )
    
    # List all
    all_scenarios = list_scenarios(db_conn)
    assert len(all_scenarios) == 2
    
    # Filter by difficulty
    easy_scenarios = list_scenarios(db_conn, difficulty="easy")
    assert len(easy_scenarios) == 1
    assert easy_scenarios[0].id == "test-scenario-1"
    
    # Filter by source
    generated_scenarios = list_scenarios(db_conn, source="generated")
    assert len(generated_scenarios) == 1
    assert generated_scenarios[0].id == "test-scenario-2"
    
    # Filter by both
    none_scenarios = list_scenarios(db_conn, difficulty="easy", source="generated")
    assert len(none_scenarios) == 0

def test_list_scenarios_summary_content(db_conn: sqlite3.Connection, sample_scenario: ScenarioSchema):
    embedding = b"\x00" * 1536
    upsert_scenario(
        conn=db_conn,
        scenario=sample_scenario,
        embedding=embedding,
        source="bundled",
        title="Scenario 1",
        difficulty="easy",
        tags=["tag1", "tag2"]
    )
    
    summaries = list_scenarios(db_conn)
    assert len(summaries) == 1
    s = summaries[0]
    assert s.id == sample_scenario.id
    assert s.title == "Scenario 1"
    assert s.difficulty == "easy"
    assert s.source == "bundled"
    assert s.tags == ["tag1", "tag2"]
    assert isinstance(s.created_at, str)
