# Data Model: eduops Core Platform

**Spec**: [specs/001-core-platform/spec.md](specs/001-core-platform/spec.md) | **Date**: 2026-03-04

---

## Overview

eduops uses a single SQLite database at `~/.eduops/eduops.db` with exactly four tables (constitution constraint). No ORM — raw `sqlite3` module. No migrations in v1; schema changes delete and recreate the file.

---

## Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────┐
│  scenarios   │       │   sessions   │
├──────────────┤       ├──────────────┤
│ id (PK)      │◄──────│ scenario_id  │
│ title        │  1:N  │ id (PK)      │
│ description  │       │ status       │
│ difficulty   │       │ workspace_   │
│ tags         │       │   path       │
│ source       │       │ started_at   │
│ schema_json  │       │ completed_at │
│ embedding    │       │ review_text  │
│ created_at   │       └──────┬───────┘
└──────────────┘              │
                              │ 1:N
                    ┌─────────┴─────────┐
                    │                   │
              ┌─────┴──────┐    ┌───────┴────────┐
              │  hint_log  │    │    chat_log    │
              ├────────────┤    ├────────────────┤
              │ id (PK)    │    │ id (PK)        │
              │ session_id │    │ session_id     │
              │ hint_index │    │ role           │
              │ shown_at   │    │ content        │
              └────────────┘    │ created_at     │
                                └────────────────┘
```

---

## Table: `scenarios`

The scenario catalogue. Populated at startup from bundled JSON files; supplemented at runtime when the user generates a new scenario.

| Column        | Type | Constraints                                             | Notes                                                             |
| ------------- | ---- | ------------------------------------------------------- | ----------------------------------------------------------------- |
| `id`          | TEXT | PRIMARY KEY                                             | UUID v4                                                           |
| `title`       | TEXT | NOT NULL                                                | Human-readable scenario title                                     |
| `description` | TEXT | NOT NULL                                                | Task brief shown to the user                                      |
| `difficulty`  | TEXT | NOT NULL, CHECK(difficulty IN ('easy','medium','hard')) | User-selected or bundled                                          |
| `tags`        | TEXT | NOT NULL                                                | JSON array serialised as string, e.g. `["volumes","bind-mounts"]` |
| `source`      | TEXT | NOT NULL, CHECK(source IN ('bundled','generated'))      | Origin of the scenario                                            |
| `schema_json` | TEXT | NOT NULL                                                | Full scenario JSON blob (validated against typed schema)          |
| `embedding`   | BLOB | NOT NULL                                                | 384-dim float32 vector, 1536 bytes raw (`all-MiniLM-L6-v2`)       |
| `created_at`  | TEXT | NOT NULL                                                | ISO 8601 timestamp                                                |

**Indexes**:

- PRIMARY KEY on `id`
- INDEX on `source` (for filtering bundled vs generated)
- INDEX on `difficulty` (for catalogue filtering)

**Validation Rules**:

- `difficulty` must be one of: `easy`, `medium`, `hard`
- `source` must be one of: `bundled`, `generated`
- `tags` must be a valid JSON array of strings
- `schema_json` must be valid JSON conforming to the Scenario JSON Schema (typed actions, typed checks, approved images)
- `embedding` must be exactly 1536 bytes (384 × 4-byte float32)

**Lifecycle**:

- Bundled scenarios are upserted on every startup (insert or update by `id`)
- Generated scenarios are inserted after LLM generation + validation + embedding computation
- Scenarios are never deleted in v1

---

## Table: `sessions`

One row per scenario attempt. The session `id` is also used as the Docker resource label value (`eduops.session=<uuid>`).

| Column           | Type | Constraints                                                   | Notes                                               |
| ---------------- | ---- | ------------------------------------------------------------- | --------------------------------------------------- |
| `id`             | TEXT | PRIMARY KEY                                                   | UUID v4, also used as Docker label value            |
| `scenario_id`    | TEXT | NOT NULL, FOREIGN KEY → scenarios.id                          | Which scenario is being attempted                   |
| `status`         | TEXT | NOT NULL, CHECK(status IN ('active','completed','abandoned')) | Current session state                               |
| `workspace_path` | TEXT | NOT NULL                                                      | Absolute path: `~/.eduops/workspaces/<session-id>/` |
| `started_at`     | TEXT | NOT NULL                                                      | ISO 8601 timestamp                                  |
| `completed_at`   | TEXT |                                                               | ISO 8601 timestamp, NULL until session ends         |
| `review_text`    | TEXT |                                                               | LLM review output, NULL until successful submit     |

**Indexes**:

- PRIMARY KEY on `id`
- INDEX on `status` (for active session lookup and stale detection)
- INDEX on `scenario_id` (for session history per scenario)

**Validation Rules**:

- `status` must be one of: `active`, `completed`, `abandoned`
- Only one session may have `status = 'active'` at any time (enforced in application logic, not DB constraint)
- `workspace_path` must be under `~/.eduops/workspaces/`
- `completed_at` must be NULL when `status = 'active'` and NOT NULL when `status` is `completed` or `abandoned`

**State Transitions**:

```
                    ┌─────────┐
     create ──────► │ active  │
                    └────┬────┘
                         │
              ┌──────────┼──────────┐
              ▼                     ▼
     ┌────────────┐        ┌───────────┐
     │ completed  │        │ abandoned │
     └────────────┘        └───────────┘
```

- `active` → `completed`: User submits, all checks pass, review generated, cleanup runs
- `active` → `abandoned`: User clicks "End session" or process terminates with cleanup
- No reverse transitions. A completed or abandoned session is final.
- On stale recovery (crash without cleanup), `active` sessions found in DB are cleaned up and their status updated to `abandoned`.

---

## Table: `hint_log`

Tracks which hints have been shown in a session, preventing the same hint from being repeated.

| Column       | Type    | Constraints                         | Notes                                              |
| ------------ | ------- | ----------------------------------- | -------------------------------------------------- |
| `id`         | INTEGER | PRIMARY KEY AUTOINCREMENT           | Row ID                                             |
| `session_id` | TEXT    | NOT NULL, FOREIGN KEY → sessions.id | Which session                                      |
| `hint_index` | INTEGER | NOT NULL                            | Position in the scenario's `hints` array (0-based) |
| `shown_at`   | TEXT    | NOT NULL                            | ISO 8601 timestamp                                 |

**Indexes**:

- PRIMARY KEY on `id`
- UNIQUE INDEX on `(session_id, hint_index)` — a hint index can only be shown once per session

**Validation Rules**:

- `hint_index` must be >= 0 and < length of the scenario's `hints` array
- The UNIQUE constraint prevents duplicate hint display

---

## Table: `chat_log`

Full message history for sessions. Enables UI chat restoration on page reload and provides context for LLM calls.

| Column       | Type    | Constraints                                   | Notes                                 |
| ------------ | ------- | --------------------------------------------- | ------------------------------------- |
| `id`         | INTEGER | PRIMARY KEY AUTOINCREMENT                     | Row ID                                |
| `session_id` | TEXT    | NOT NULL, FOREIGN KEY → sessions.id           | Which session                         |
| `role`       | TEXT    | NOT NULL, CHECK(role IN ('user','assistant')) | Message author                        |
| `content`    | TEXT    | NOT NULL                                      | Message text (plain text or markdown) |
| `created_at` | TEXT    | NOT NULL                                      | ISO 8601 timestamp                    |

**Indexes**:

- PRIMARY KEY on `id`
- INDEX on `session_id` (for loading session chat history)
- INDEX on `(session_id, created_at)` (for ordered history retrieval)

**Validation Rules**:

- `role` must be one of: `user`, `assistant`
- Messages are append-only — never updated or deleted
- Chat history is loaded in `created_at` order when building LLM context

---

## Schema DDL

```sql
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

CREATE INDEX IF NOT EXISTS idx_scenarios_source ON scenarios(source);
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

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_scenario_id ON sessions(scenario_id);

CREATE TABLE IF NOT EXISTS hint_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    hint_index INTEGER NOT NULL,
    shown_at   TEXT NOT NULL,
    UNIQUE(session_id, hint_index)
);

CREATE TABLE IF NOT EXISTS chat_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_log_session ON chat_log(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_log_session_time ON chat_log(session_id, created_at);
```

---

## Typed Domain Objects (Python)

These are the in-memory representations used by the backend. They are **not** ORM models — they are plain dataclasses/Pydantic models used for validation and serialisation.

### Setup Actions (discriminated union)

```python
from typing import Literal
from pydantic import BaseModel

class PullImage(BaseModel):
    action: Literal["pull_image"]
    image: str

class BuildImage(BaseModel):
    action: Literal["build_image"]
    tag: str
    dockerfile_content: str

class CreateNetwork(BaseModel):
    action: Literal["create_network"]
    name: str
    driver: str = "bridge"

class CreateVolume(BaseModel):
    action: Literal["create_volume"]
    name: str

class RunContainer(BaseModel):
    action: Literal["run_container"]
    image: str
    name: str
    ports: dict[str, str] = {}
    volumes: dict[str, str] = {}
    network: str | None = None
    env: dict[str, str] = {}
    command: str | None = None
    detach: bool = True

SetupAction = PullImage | BuildImage | CreateNetwork | CreateVolume | RunContainer
```

### Success Checks (discriminated union)

```python
class ContainerRunning(BaseModel):
    type: Literal["container_running"]
    name: str

class PortResponds(BaseModel):
    type: Literal["port_responds"]
    port: int
    path: str = "/"
    expect_status: int = 200
    expect_body: str | None = None

class DockerExec(BaseModel):
    type: Literal["docker_exec"]
    container: str
    command: list[str]  # MUST be list[str], never a bare string
    expect_stdout: str

class FileInWorkspace(BaseModel):
    type: Literal["file_in_workspace"]
    path: str  # relative to workspace root
    expect_content: str | None = None

SuccessCheck = ContainerRunning | PortResponds | DockerExec | FileInWorkspace
```

### Workspace File

```python
class WorkspaceFile(BaseModel):
    path: str  # relative to workspace root
    content: str
```

### Scenario Schema

```python
class ScenarioSchema(BaseModel):
    id: str  # UUID
    title: str
    description: str
    difficulty: Literal["easy", "medium", "hard"]
    tags: list[str]
    workspace_files: list[WorkspaceFile] = []
    setup_actions: list[SetupAction]
    success_checks: list[SuccessCheck]
    hints: list[str] = []
    review_context: str = ""
```

### Session

```python
from datetime import datetime

class Session(BaseModel):
    id: str  # UUID, also Docker label value
    scenario_id: str
    status: Literal["active", "completed", "abandoned"]
    workspace_path: str
    started_at: datetime
    completed_at: datetime | None = None
    review_text: str | None = None
```

### Check Result

```python
class CheckResult(BaseModel):
    check_type: str
    check_name: str  # human-readable identifier
    passed: bool
    message: str
```

### Review (LLM output)

```python
class Review(BaseModel):
    what_went_well: list[str]
    what_could_improve: list[str]
    next_steps: list[str]
```

---

## Embedding Storage & Search

- **Storage**: 384-dim float32 vector stored as BLOB (1536 bytes) in `scenarios.embedding`
- **Pre-computed**: Bundled scenarios ship with embeddings in `eduops/data/scenario_embeddings.json` (base64-encoded)
- **Runtime computation**: Generated scenarios get embeddings at creation time via `sentence-transformers[onnx]` with `all-MiniLM-L6-v2`
- **Search**: Query embedding computed at search time, cosine similarity against all scenario embeddings, results ranked by score
- **Implementation**: Load all embeddings into memory at startup (10–1000 scenarios × 1.5 KB = negligible). Cosine similarity via numpy or manual dot product. No vector DB needed.

---

## Configuration (not in SQLite)

LLM configuration lives in `~/.eduops/config.toml`, not in the database:

```toml
[llm]
provider = "openrouter"         # openai | gemini | openrouter | custom
api_key = "sk-or-v1-..."
model = "openai/gpt-4o"
base_url = ""                   # optional; auto-derived from provider

[images]
approved = [                    # extensible approved image list
    "nginx:alpine",
    "httpd:alpine",
    "python:3.11-slim",
    "alpine:3",
    "busybox:latest",
    "node:20-alpine",
]
```

```python
from pydantic import BaseModel

class LLMConfig(BaseModel):
    provider: Literal["openai", "gemini", "openrouter", "custom"]
    api_key: str
    model: str
    base_url: str = ""

class ImagesConfig(BaseModel):
    approved: list[str] = [
        "nginx:alpine", "httpd:alpine", "python:3.11-slim",
        "alpine:3", "busybox:latest", "node:20-alpine",
    ]

class Config(BaseModel):
    llm: LLMConfig
    images: ImagesConfig = ImagesConfig()
```
