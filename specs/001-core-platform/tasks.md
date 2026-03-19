# Tasks: eduops Core Platform

**Input**: Design documents from `/specs/001-core-platform/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Not explicitly requested — test tasks are omitted. Add them if TDD is desired.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. Each task targets a single module/function/component — the smallest viable implementation unit.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/src/eduops/`, `backend/tests/`
- **Frontend**: `frontend/src/`
- Follows the web app convention from plan.md

## Modularity Principles

The design documents (plan.md, data-model.md, contracts/) enforce modularity through:

- **Layered architecture**: API → Services → Models → DB (no layer skipping)
- **Single-responsibility services**: Each service file owns one concern (catalogue, docker_exec, checks, cleanup, coaching, embedding, generation, logs)
- **Typed boundaries**: Pydantic discriminated unions enforce typed action/check dispatch — no stringly-typed logic
- **Story isolation**: Frontend API functions are added per-story (not all upfront), so each story only introduces what it needs
- **Clean interfaces**: API layer is thin (validation + routing), services hold business logic, models hold data shapes

Tasks below reinforce this by: one function per task where possible, services split from their API endpoints, no placeholder files, and frontend client functions scoped to their user story.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency declaration, and basic directory scaffolding

- [x] T001 Create backend package in `backend/` — `pyproject.toml` with hatchling build, dependencies (fastapi, uvicorn[standard], docker, sentence-transformers[onnx], openai, httpx, sse-starlette, tomli, pydantic), [dev] extras (pytest, ruff, mypy), entry point `eduops = "eduops.cli:main"`; `src/eduops/__init__.py` with version; `src/eduops/__main__.py` invoking `cli.main()`
- [x] T002 [P] Scaffold frontend Vite + React + TypeScript project in `frontend/` — `package.json`, `vite.config.ts` (@ path alias, Tailwind CSS plugin, /api proxy to localhost:7337), `tsconfig.json`, `index.html`
- [x] T003 [P] Initialise shadcn/ui in `frontend/` — `components.json`, Tailwind CSS v4 with `@tailwindcss/vite`, install base components (button, card, badge, input, scroll-area, separator, dialog, toast) in `frontend/src/components/ui/`

- [x] T004 [P] Create frontend routing skeleton in `frontend/src/main.tsx` and `frontend/src/App.tsx` — react-router BrowserRouter with routes: `/` → Home, `/session/:id` → Session
- [x] T005 [P] Define frontend TypeScript types mirroring API contracts in `frontend/src/types/index.ts` — Scenario, ScenarioDetail, ScenarioSearchResult, Session, ChatMessage, CheckResult, Review, HealthStatus, SSE event types
- [x] T006 [P] Create `backend/tests/conftest.py` with shared pytest fixtures (temp SQLite DB path, test FastAPI client via httpx.AsyncClient)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Config & CLI

- [x] T007 [P] Define Config, LLMConfig, and ImagesConfig Pydantic models in `backend/src/eduops/config.py` — LLMConfig (provider, api_key, model, base_url), ImagesConfig with default approved list, top-level Config aggregating both
- [x] T008 Implement `load_config()` and `save_config()` TOML functions in `backend/src/eduops/config.py` — read/write `~/.eduops/config.toml`, handle missing file gracefully, derive `base_url` from provider (openai → default, gemini → googleapis, openrouter → openrouter.ai, custom → user-provided)
- [x] T018 Implement FastAPI app factory in `backend/src/eduops/app.py` — `create_app()` mounting API routers under `/api` prefix, serve frontend static files from `static/` directory with `StaticFiles(html=True)`, configure CORS for dev
- [x] T009 Implement CLI argument parsing and uvicorn launch in `backend/src/eduops/cli.py` — parse `eduops start` command with optional `--port` flag, launch `uvicorn` pointing to `eduops.app:app` on port 7337 (depends on T018)
- [x] T010 Implement interactive first-run LLM setup prompt in `backend/src/eduops/cli.py` — detect missing config, prompt for provider → API key → model, call `save_config()` to write `~/.eduops/config.toml`
- [x] T011 [P] Implement Docker availability check utility in `backend/src/eduops/cli.py` — `check_docker()` calling `docker.from_env().ping()`, return clear error message if Docker daemon unreachable; call before server launch

### Database

- [x] T012 [P] Implement SQLite schema DDL and `init_db()` in `backend/src/eduops/db.py` — create four tables (scenarios, sessions, hint_log, chat_log) per schema from data-model.md, ensure idempotent with IF NOT EXISTS, create all indexes
- [x] T013 Implement SQLite query helpers in `backend/src/eduops/db.py` — `get_db(path)` context manager yielding connection with row_factory, `execute()`, `fetchone()`, `fetchall()` parameterised query wrappers

### Domain Models

- [x] T014 [P] Define SetupAction discriminated union in `backend/src/eduops/models/scenario.py` — PullImage, BuildImage, CreateNetwork, CreateVolume, RunContainer Pydantic models with `action` literal discriminator field
- [x] T015 [P] Define SuccessCheck discriminated union in `backend/src/eduops/models/scenario.py` — ContainerRunning, PortResponds, DockerExec (command as `list[str]`), FileInWorkspace Pydantic models with `type` literal discriminator field
- [x] T016 Define ScenarioSchema and WorkspaceFile models in `backend/src/eduops/models/scenario.py` — ScenarioSchema aggregating setup_actions, expected_containers (`list[str]`, default `[]`), success_checks, hints, review_context, workspace_files; `validate_approved_images(schema, approved_list)` function checking all image references against approved list
- [x] T017 [P] Define Session, CheckResult, and Review Pydantic models in `backend/src/eduops/models/session.py` — Session with status enum (active/completed/abandoned), CheckResult with check_type/check_name/passed/message, Review with what_went_well/what_could_improve/next_steps (each a list of strings)

### Application Shell

- [x] T019 Implement lifespan context manager in `backend/src/eduops/app.py` — async context manager calling `init_db()` on startup and yielding; shutdown hook placeholder; wire into `create_app(lifespan=...)`
- [x] T020 Implement `GET /api/health` endpoint in `backend/src/eduops/api/health.py` — return Docker status, LLM configured flag, active session ID or null, scenario count per contracts/api.md
- [x] T021 [P] Create base frontend HTTP client with health function in `frontend/src/services/api.ts` — typed fetch wrapper with base URL `/api`, error handling, `getHealth()` function
- [x] T022 [P] Implement frontend SSE client in `frontend/src/services/sse.ts` — `connectLogStream(sessionId)` returning EventSource wrapper with typed handlers for `log`, `container_started`, `container_exited`, `dropped`, `session_ended` events, auto-reconnect

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Browse and Start a Bundled Scenario (Priority: P1) 🎯 MVP

**Goal**: A learner installs eduops, runs it, opens the browser, browses the scenario catalogue, selects a scenario, and the platform sets up the Docker environment with live log streaming.

**Independent Test**: Install the package, run `eduops start`, open `localhost:7337`, select a bundled scenario, verify Docker containers are created with correct labels, confirm the log panel streams live output.

### Catalogue Service

- [x] T023 [P] [US1] Implement `load_bundled_scenarios()` in `backend/src/eduops/services/catalogue.py` — read all JSON files from `backend/src/eduops/scenarios/` directory, parse each into ScenarioSchema, return list
- [x] T024 [US1] Implement `upsert_scenario()` in `backend/src/eduops/services/catalogue.py` — insert-or-update a scenario row in the DB by ID, store serialised schema_json and embedding BLOB
- [x] T025 [US1] Implement `list_scenarios()` and `get_scenario()` in `backend/src/eduops/services/catalogue.py` — list with optional difficulty/source filters, get by ID returning full scenario or None

### Scenario API

- [ ] T026 [US1] Implement `GET /api/scenarios` endpoint in `backend/src/eduops/api/scenarios.py` — list scenarios with optional `difficulty` and `source` query params, return scenario summaries (excluding schema_json)
- [ ] T027 [US1] Implement `GET /api/scenarios/{scenario_id}` endpoint in `backend/src/eduops/api/scenarios.py` — return scenario detail (excluding schema_json per contract), 404 for unknown IDs

### Docker Action Executor

- [ ] T028 [P] [US1] Implement image and resource action handlers in `backend/src/eduops/services/docker_exec.py` — `handle_pull_image()` calling `client.images.pull()`, `handle_build_image()` calling `client.images.build()`, `handle_create_network()` calling `client.networks.create()`, `handle_create_volume()` calling `client.volumes.create()`; all label resources with `eduops.session=<session_id>`
- [ ] T029 [US1] Implement `handle_run_container()` in `backend/src/eduops/services/docker_exec.py` — translate RunContainer action to `client.containers.run()` with port mapping, volume binds, network, env vars, command; label with `eduops.session=<session_id>`; detach mode
- [ ] T030 [US1] Implement `execute_setup_actions()` orchestrator in `backend/src/eduops/services/docker_exec.py` — iterate typed actions, resolve `{{workspace}}` template variable in all string fields, dispatch to correct handler, track created resources, rollback all on failure

### Session Service

- [ ] T031 [US1] Implement `create_session()` in `backend/src/eduops/services/session.py` — generate UUID, create workspace directory at `~/.eduops/workspaces/<session-id>/`, write workspace_files to disk, call `execute_setup_actions()`, insert session row with status `active`
- [ ] T032 [US1] Implement `get_active_session()` and single-session enforcement in `backend/src/eduops/services/session.py` — query DB for `status='active'` session, return Session or None; raise error if active session already exists when creating

### Session API

- [ ] T033 [US1] Implement `POST /api/sessions` endpoint in `backend/src/eduops/api/sessions.py` — validate scenario exists, check no active session (409), call `create_session()`, return 201 with session + scenario info per contracts/api.md
- [ ] T034 [US1] Implement `GET /api/sessions/active` endpoint in `backend/src/eduops/api/sessions.py` — return active session with scenario info, or 404

### SSE Log Streaming

- [ ] T035 [P] [US1] Implement single-container log follower thread in `backend/src/eduops/services/logs.py` — `_follow_container_logs(container, queue, loop, cancel_event)` reading `container.logs(stream=True, follow=True, timestamps=True, tail=100)`, pushing LogEvent objects to asyncio.Queue via `loop.call_soon_threadsafe()`, handling container removal and cancel_event
- [ ] T036 [US1] Implement container discovery and Docker events watcher in `backend/src/eduops/services/logs.py` — discover existing containers by label AND by expected_containers names (from scenario schema), spawn follower thread per container; watch `client.events()` (unfiltered) in a thread for `start`/`die` events, match against label OR expected names, dynamically add/remove followers
- [ ] T037 [US1] Implement log multiplexer async generator in `backend/src/eduops/services/logs.py` — `stream_session_logs(session_id, expected_containers)` async generator consuming from shared asyncio.Queue, yielding SSE-formatted events; handle QueueFull backpressure with drop+warn; cleanup all threads and cancel_event in `finally` block per research.md Topic 3
- [ ] T038 [US1] Implement `GET /api/sessions/{session_id}/logs` SSE endpoint in `backend/src/eduops/api/logs.py` — wrap `stream_session_logs()` with `EventSourceResponse(ping=15, send_timeout=30)`, set `Cache-Control` and `X-Accel-Buffering` headers, check `request.is_disconnected()` as safety guard

### Embedding Service

- [ ] T039 [P] [US1] Implement embedding service in `backend/src/eduops/services/embedding.py` — `load_model()` initialising `SentenceTransformer("all-MiniLM-L6-v2", backend="onnx")` as cached singleton, `compute_embedding(text)` returning 384-dim float32 bytes, `decode_embedding(blob)` converting BLOB to numpy array

### Bundled Content

- [ ] T040 [P] [US1] Create bundled scenario JSON files 1–4 in `backend/src/eduops/scenarios/` — (1) running containers (easy), (2) port bindings (easy), (3) bind mounts (easy), (4) named volumes (medium); each with typed setup_actions, expected_containers, success_checks, hints, review_context
- [ ] T041 [P] [US1] Create bundled scenario JSON files 5–7 in `backend/src/eduops/scenarios/` — (5) Dockerfile basics (easy), (6) image building (medium), (7) container debugging with build_image fault injection (medium); each with expected_containers listing user-created container names
- [ ] T042 [P] [US1] Create bundled scenario JSON files 8–10 in `backend/src/eduops/scenarios/` — (8) environment variables (medium), (9) networking two containers (hard), (10) multi-step workflows (hard); each with expected_containers; collectively all 10 must exercise all four check types and all three difficulty levels
- [ ] T043 [P] [US1] Create embedding precomputation script in `backend/scripts/compute_embeddings.py` — optional dev utility to verify embedding dimensions and model consistency; not required at runtime since embeddings are computed at startup by the embedding model

### App Wiring

- [ ] T044 [US1] Wire bundled scenario loading and embedding init into app lifespan in `backend/src/eduops/app.py` — on startup: load embedding model, call `load_bundled_scenarios()`, compute embeddings for all bundled scenarios, upsert all into DB

### Frontend API Client (US1)

- [ ] T045 [P] [US1] Add scenario and session API functions to `frontend/src/services/api.ts` — `getScenarios(difficulty?, source?)`, `getScenario(id)`, `createSession(scenarioId)`, `getActiveSession()`

### Frontend Components (US1)

- [ ] T046 [P] [US1] Implement ScenarioCatalogue component in `frontend/src/components/ScenarioCatalogue.tsx` — fetch scenarios via `getScenarios()`, render list of ScenarioCard components, difficulty filter dropdown
- [ ] T047 [P] [US1] Implement ScenarioCard component in `frontend/src/components/ScenarioCard.tsx` — title, truncated description, color-coded difficulty badge (green/yellow/red), tags as badges, "Start" button
- [ ] T048 [US1] Implement Home page in `frontend/src/pages/Home.tsx` — render ScenarioCatalogue, handle "Start" click → `createSession()` → navigate to `/session/:id`, loading state, error toasts (409/422)
- [ ] T049 [P] [US1] Implement LogPanel component in `frontend/src/components/LogPanel.tsx` — connect SSE via sse.ts client, render log lines with container name prefix (color-coded), auto-scroll, show start/exit/dropped events, handle reconnection
- [ ] T050 [US1] Implement ActiveSession layout component in `frontend/src/components/ActiveSession.tsx` — scenario title/description/difficulty/workspace path header, LogPanel, placeholder slot for ChatPanel (wired in US3); disabled "Submit" and "End Session" button placeholders (wired in US2 T065 and US6 T092 respectively)
- [ ] T051 [US1] Implement Session page in `frontend/src/pages/Session.tsx` — check active session via `getActiveSession()` on mount, redirect to Home if mismatch or missing, render ActiveSession

**Checkpoint**: User Story 1 complete — browse catalogue, start scenario, see live logs, work in own terminal

---

## Phase 4: User Story 2 — Submit a Solution and Receive AI Review (Priority: P2)

**Goal**: The user clicks Submit, deterministic checks run, and on success the LLM generates a review. The session stays active so the user can inspect their work alongside the feedback. Cleanup is deferred to explicit "End Session."

**Independent Test**: With an active scenario, complete the task, click Submit, verify checks pass, verify LLM review appears, verify containers remain running and workspace intact, verify the user can still chat. Then click "End Session" and verify full cleanup.

### Success Checks

- [ ] T052 [P] [US2] Implement `check_container_running()` and `check_port_responds()` handlers in `backend/src/eduops/services/checks.py` — container_running: `client.containers.get(name).status`; port_responds: `httpx.get()` checking status code and optional body match

- [ ] T053 [US2] Implement `check_docker_exec()` and `check_file_in_workspace()` handlers in `backend/src/eduops/services/checks.py` — docker_exec: `container.exec_run(command)` comparing stdout to expected; file_in_workspace: read file at workspace path, optionally check content
- [ ] T054 [US2] Implement synchronous `run_checks()` orchestrator in `backend/src/eduops/services/checks.py` — dispatch each typed SuccessCheck to its handler, 30-second timeout with 2-second polling loop per check, collect and return list of CheckResult objects; keep blocking Docker/timeout work inside this sync function so it can be run in a worker thread from the API layer without blocking the ASGI event loop

### Cleanup Service

- [ ] T055 [P] [US2] Implement `cleanup_session()` in `backend/src/eduops/services/cleanup.py` — accept optional `keep_workspace: bool` (default `False`); deterministic order: force-remove expected_containers by name (skip if not found) → force-remove labelled containers → remove labelled networks → remove labelled volumes → if not `keep_workspace`, delete workspace directory → update session status in DB (`completed` if `review_text IS NOT NULL`, else `abandoned`); labelled resources via filter `eduops.session=<id>`, expected containers by name from scenario schema_json; Docker images are NOT removed (reused across sessions)
- [ ] T056 [US2] Implement `cleanup_stale_sessions()` in `backend/src/eduops/services/cleanup.py` — query DB for `status='active'` sessions, load scenario schema_json for expected_containers, call `cleanup_session()` for each (covering both labelled and expected-name resources), log recovered sessions
- [ ] T057 [US2] Register SIGINT/SIGTERM signal handlers for cleanup in `backend/src/eduops/services/cleanup.py` — on signal, run `cleanup_session()` for active session then exit; integrate as importable `register_signal_handlers()` function

### LLM Client & Review

- [ ] T058 [P] [US2] Implement LLM client initialisation in `backend/src/eduops/services/llm_coaching.py` — `get_llm_client(config)` returning `openai.AsyncOpenAI(api_key=config.llm.api_key, base_url=config.llm.base_url)` as a cached instance; base_url is already derived from provider by config.py (T008)
- [ ] T059 [US2] Implement `generate_review()` in `backend/src/eduops/services/llm_coaching.py` — accept scenario context, docker inspect data, and container logs; build messages with review system prompt; call `client.chat.completions.create()`; parse response into Review model (what_went_well, what_could_improve, next_steps)
- [ ] T060 [P] [US2] Create review system prompt template in `backend/src/eduops/prompts/review_system.txt` — instruct LLM to evaluate Docker work and return structured JSON with what_went_well, what_could_improve, next_steps

### Submit API

- [ ] T061 [US2] Implement `POST /api/sessions/{session_id}/submit` in `backend/src/eduops/api/sessions.py` — validate session active, run `run_checks()` via `await asyncio.to_thread(...)` so blocking check timeouts do not block FastAPI's event loop; if all pass: collect inspect data + logs → `generate_review()` → persist review (overwrite any previous review) → return session_status `active` with review (no cleanup, no status change — containers keep running, workspace intact); if any fail: return checks with null review, status stays active. Re-submission is allowed so users can fix issues and get a fresh AI evaluation

### Frontend (US2)

- [ ] T062 [P] [US2] Add `submitSession()` API function to `frontend/src/services/api.ts` — POST to /api/sessions/:id/submit, typed response with checks array, review, session_status
- [ ] T063 [P] [US2] Implement SubmitButton component in `frontend/src/components/SubmitButton.tsx` — loading spinner during check execution, display pass/fail results per check with detail messages
- [ ] T064 [P] [US2] Implement ReviewPanel component in `frontend/src/components/ReviewPanel.tsx` — three sections: what went well (green), what could improve (amber), next steps (blue)
- [ ] T065 [US2] Integrate submit flow and review display into `frontend/src/components/ActiveSession.tsx` — wire SubmitButton, show checks inline, render ReviewPanel on success; keep session page active (do NOT navigate to Home) so user can inspect their work, chat with the AI coach, fix issues, and re-submit for a fresh review

**Checkpoint**: User Stories 1 and 2 complete — full learning loop: browse → start → work → submit → review → inspect → end session → cleanup

---

## Phase 5: User Story 3 — Ask for Help During a Scenario (Priority: P3)

**Goal**: The user types a question in the chat panel and receives Socratic coaching from the LLM. Hints are tracked to prevent repetition. Chat history persists across page reloads.

**Independent Test**: With an active scenario, type a question, verify LLM responds with guidance, ask a follow-up, verify hint history prevents repeats, reload browser and confirm chat restores.

### Chat Persistence

- [ ] T066 [P] [US3] Implement chat history DB helpers in `backend/src/eduops/services/llm_coaching.py` — `get_chat_history(db, session_id)` returning ordered messages, `save_message(db, session_id, role, content)` inserting into chat_log table

### Hint Tracking

- [ ] T067 [US3] Implement hint tracking functions in `backend/src/eduops/services/llm_coaching.py` — `get_shown_hints(db, session_id)` querying hint_log, `get_next_hint_index(hints, shown_indices)` selecting the next unseen hint deterministically (lowest unseen index), and `record_hint(db, session_id, hint_index)` inserting with UNIQUE constraint

### Hint Generation

- [ ] T068 [US3] Implement `generate_hint()` in `backend/src/eduops/services/llm_coaching.py` — build messages with system prompt (Socratic by default, direct if `show_answer=True`); in Socratic mode load shown hint indices, select the next unseen hint from the scenario `hints` array (if any), inject that hint text into the prompt, call LLM via `get_llm_client()`, persist the assistant message, then record the consumed `hint_index`; if no hints remain, continue without hint injection

### Chat API

- [ ] T069 [US3] Implement `POST /api/sessions/{session_id}/chat` endpoint in `backend/src/eduops/api/chat.py` — accept `{message, show_answer}`, validate session active, persist the user message, load history + scenario hints, call `generate_hint()`, and return the persisted assistant response
- [ ] T070 [US3] Implement `GET /api/sessions/{session_id}/chat` endpoint in `backend/src/eduops/api/chat.py` — return full ordered chat history for session, 404 if session not found

### Prompt Templates

- [ ] T071 [P] [US3] Create coaching prompt templates in `backend/src/eduops/prompts/` — `coaching_socratic.txt` (forbid direct answers, encourage guiding questions) and `coaching_direct.txt` (direct answer mode for "Show Answer")

### Frontend (US3)

- [ ] T072 [P] [US3] Add chat API functions to `frontend/src/services/api.ts` — `sendChat(sessionId, message, showAnswer)` and `getChatHistory(sessionId)`
- [ ] T073 [P] [US3] Implement ChatMessage component in `frontend/src/components/ChatMessage.tsx` — role indicator (user right, assistant left), markdown rendering for assistant, timestamp
- [ ] T074 [US3] Implement ChatPanel component in `frontend/src/components/ChatPanel.tsx` — load history on mount, ChatMessage list in scroll-area, input field, send via `sendChat()`, loading indicator, "Show Answer" toggle, auto-scroll
- [ ] T075 [US3] Integrate ChatPanel into `frontend/src/components/ActiveSession.tsx` — split layout with LogPanel (left) and ChatPanel (right), both independently scrollable

**Checkpoint**: User Stories 1–3 complete — full coaching experience with Socratic hints and chat persistence

---

## Phase 6: User Story 4 — Generate a Custom Scenario via Chat (Priority: P4)

**Goal**: The user describes a desired scenario, selects a difficulty, and the platform generates a validated, embeddable scenario via the LLM.

**Independent Test**: Describe a scenario, verify LLM returns valid JSON, verify it passes validation, verify it appears in the catalogue with an embedding, verify it can be started.

### Scenario Generation Service

- [ ] T076 [P] [US4] Implement LLM scenario generation prompt builder in `backend/src/eduops/services/generation.py` — `_build_generation_prompt(description, difficulty, approved_images)` constructing messages with ScenarioSchema JSON schema, approved image list, four allowed check types, and example scenario
- [ ] T077 [US4] Implement scenario response validation in `backend/src/eduops/services/generation.py` — `_validate_generated_scenario(schema_json, approved_images)` checking: all images in approved list, all action types recognised, all check types are the four allowed, `docker_exec` commands are `list[str]`, `expected_containers` is present and is `list[str]`; return list of validation errors
- [ ] T078 [US4] Implement `generate_scenario()` with retry in `backend/src/eduops/services/generation.py` — call LLM, parse JSON, validate; on failure: retry once feeding errors back; on second failure: raise with errors; on success: compute embedding, persist to DB via `upsert_scenario()`

### Generation API

- [ ] T079 [US4] Implement `POST /api/scenarios/generate` endpoint in `backend/src/eduops/api/scenarios.py` — accept `{description, difficulty}`, call `generate_scenario()`, return 201 (excluding schema_json), 422 on validation failure, 502 on LLM unreachable

### Prompt Template

- [ ] T080 [P] [US4] Create generation system prompt template in `backend/src/eduops/prompts/generation_system.txt` — full JSON schema (including `expected_containers` field), approved image list, four check types, example scenario, constraint instructions

### Frontend (US4)

- [ ] T081 [P] [US4] Add `generateScenario()` API function to `frontend/src/services/api.ts` — POST to /api/scenarios/generate with description and difficulty
- [ ] T082 [P] [US4] Implement GenerateScenario form component in `frontend/src/components/GenerateScenario.tsx` — description textarea, difficulty selector, "Generate" button, loading state, result display or validation errors, "Start" button for immediate start
- [ ] T083 [US4] Integrate generation UI into `frontend/src/pages/Home.tsx` — "Generate Custom Scenario" dialog/section, refresh catalogue on success, optionally auto-navigate to start

**Checkpoint**: User Stories 1–4 complete — users can generate infinite custom scenarios

---

## Phase 7: User Story 5 — Search Scenarios by Natural Language (Priority: P5)

**Goal**: The user types a natural-language query, and the platform returns semantically relevant scenarios ranked by similarity using local embeddings.

**Independent Test**: With bundled scenarios loaded, type "volumes," verify results ranked by semantic similarity, verify no network calls for embedding.

### Semantic Search

- [ ] T084 [US5] Implement `search_scenarios()` in `backend/src/eduops/services/catalogue.py` — compute query embedding locally via embedding service, load all scenario embeddings from DB, compute cosine similarity via numpy dot product, return results ranked by score above minimum threshold
- [ ] T085 [US5] Implement `POST /api/scenarios/search` endpoint in `backend/src/eduops/api/scenarios.py` — accept `{query}`, call `search_scenarios()`, return results with `score` field; empty array for no matches

### Frontend (US5)

- [ ] T086 [P] [US5] Add `searchScenarios()` API function to `frontend/src/services/api.ts` — POST to /api/scenarios/search with query string
- [ ] T087 [P] [US5] Implement SearchBar component in `frontend/src/components/SearchBar.tsx` — debounced input (300ms), call `searchScenarios()`, display results, clear to restore catalogue, "no results" message
- [ ] T088 [US5] Integrate SearchBar into `frontend/src/pages/Home.tsx` — above ScenarioCatalogue, search active shows results, clear restores full catalogue

**Checkpoint**: User Stories 1–5 complete — semantic search enhances discoverability

---

## Phase 8: User Story 6 — Abandon a Session and Clean Up (Priority: P6)

**Goal**: The user clicks "End session" (from active or reviewed state), all Docker resources are cleaned up (with an option to keep the workspace), and they can start a new scenario. Stale sessions from crashes are recovered on startup.

**Independent Test**: Start a scenario, click "End session," verify all session-labelled Docker resources removed, verify workspace prompt works, verify new scenario can start. Repeat with a reviewed session (submit first, then end).

### Abandon API

- [ ] T089 [US6] Implement `DELETE /api/sessions/{session_id}` endpoint in `backend/src/eduops/api/sessions.py` — validate session exists and `status='active'` (404/409), accept optional JSON body `{cleanup_workspace: bool}` (default `false`), call `cleanup_session(keep_workspace=not cleanup_workspace)`, status set to `completed` if `review_text IS NOT NULL` else `abandoned`, return per contract with `workspace_kept` field

### Stale Recovery

- [ ] T090 [US6] Wire `cleanup_stale_sessions()` into app startup lifespan in `backend/src/eduops/app.py` — call before allowing new sessions, log recovered sessions

### Frontend (US6)

- [ ] T091 [P] [US6] Add `deleteSession()` API function to `frontend/src/services/api.ts` — DELETE /api/sessions/:id with optional `{cleanup_workspace: bool}` body
- [ ] T092 [P] [US6] Implement "End Session" button with confirmation dialog in `frontend/src/components/ActiveSession.tsx` — dialog includes workspace path display and checkbox "Delete workspace files at {path}" (unchecked by default); call `deleteSession(id, {cleanup_workspace})`, show cleanup progress, navigate to Home
- [ ] T093 [US6] Handle active session state on Home page mount in `frontend/src/pages/Home.tsx` — check `getActiveSession()`, if active show banner with resume/end options, prevent new scenario start

**Checkpoint**: All 6 user stories complete — full session lifecycle with crash recovery

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final packaging

- [ ] T094 [P] Implement error boundary in `frontend/src/components/ErrorBoundary.tsx` — catch React rendering errors, user-friendly message, "reload" action
- [ ] T095 [P] Implement toast notification system in `frontend/src/App.tsx` — shadcn/ui toast for success/error/warning across all flows
- [ ] T096 [P] Add responsive layout and styling polish to `frontend/src/App.tsx` — header with eduops branding, responsive catalogue grid, mobile session layout
- [ ] T097 Implement frontend build integration in `backend/pyproject.toml` — hatchling includes `frontend/dist/` as `eduops/static/` in wheel; update app.py to resolve static path from package data
- [ ] T098 [P] Add graceful LLM degradation in `backend/src/eduops/services/llm_coaching.py` and `backend/src/eduops/services/generation.py` — catch connection errors, return 502; non-AI features work without LLM
- [ ] T099 [P] Add Docker-not-running error handling in `backend/src/eduops/services/docker_exec.py` — catch `DockerException`, report clearly; ensure health endpoint reflects Docker status
- [ ] T100 [P] Write `backend/README.md` and `frontend/README.md` with development setup workflows
- [ ] T101 Run quickstart.md validation — verify `pip install -e ".[dev]"`, `npm ci && npm run build`, `uvicorn` start, frontend proxy, `eduops start` end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **BLOCKS US2**
- **US2 (Phase 4)**: Depends on US1 (session infrastructure, docker_exec)
- **US3 (Phase 5)**: Depends on US1 session infrastructure; can parallel with US2
- **US4 (Phase 6)**: Depends on US1 embedding service + US2 LLM client
- **US5 (Phase 7)**: Depends on US1 embedding + catalogue services; can parallel with US2/US3
- **US6 (Phase 8)**: Depends on US2 cleanup service
- **Polish (Phase 9)**: Depends on all desired stories complete

### User Story Dependencies

- **US1 (P1)**: Foundational only — **MVP scope**
- **US2 (P2)**: Requires US1. Must follow.
- **US3 (P3)**: Requires US1 sessions. Can parallel with US2.
- **US4 (P4)**: Requires US1 embeddings + US2 LLM. Best after US2.
- **US5 (P5)**: Requires US1 embeddings + catalogue. Can parallel with US2/US3.
- **US6 (P6)**: Requires US2 cleanup. Best after US2.

### Within Each User Story

- Service functions before API endpoints
- API endpoints before frontend components
- Presentational components before page integration
- Story complete before moving to next priority

### Parallel Opportunities

**Setup**: T002–T006 all parallel
**Foundational**: T007, T011, T012, T014, T015, T017, T021, T022 all parallel (no cross-deps)
**US1**: T023/T028/T035/T039/T040–T043/T045–T047/T049 can run in parallel waves
**US2**: T052/T055/T058/T060/T062–T064 can run in parallel
**US3**: T066/T071–T073 can run in parallel
**US4**: T076/T080–T082 can run in parallel
**US5**: T086/T087 can run in parallel
**US6**: T091/T092 can run in parallel
**Polish**: T094–T096, T098–T100 all parallel

---

## Parallel Example: User Story 1

```
# Wave 1 — Independent services + content (all different files):
T023: load_bundled_scenarios() in services/catalogue.py
T028: image + resource action handlers in services/docker_exec.py
T035: single-container log follower in services/logs.py
T039: embedding service in services/embedding.py
T040–T042: bundled scenario JSON files (3 groups, parallel)
T043: embedding precomputation script
T045: frontend scenario + session API functions
T046–T047: ScenarioCatalogue + ScenarioCard components

# Wave 2 — Functions depending on Wave 1:
T024: upsert_scenario() in catalogue.py
T029: run_container handler in docker_exec.py
T036: container discovery + events watcher in logs.py

# Wave 3 — Orchestrators:
T025: list + get in catalogue.py
T030: execute_setup_actions() orchestrator in docker_exec.py
T037: log multiplexer async generator in logs.py
T031–T032: session service functions

# Wave 4 — API + wiring:
T026–T027: scenario API endpoints
T033–T034: session API endpoints
T038: SSE log endpoint
T044: wire into lifespan

# Wave 5 — Frontend pages:
T048: Home page
T049: LogPanel
T050: ActiveSession
T051: Session page
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T006)
2. Complete Phase 2: Foundational (T007–T022) — **CRITICAL**
3. Complete Phase 3: User Story 1 (T023–T051)
4. **STOP and VALIDATE**: Browse catalogue, start scenario, see live logs
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → **MVP!** (scenario browser + launcher + live logs)
3. Add US2 → Full learning loop (submit + review + inspect)
4. Add US3 → Interactive coaching
5. Add US4 → Infinite custom scenarios
6. Add US5 → Smart search
7. Add US6 → Clean session management
8. Polish → Production-ready package

### Single Developer Strategy

Sequential priority order: P1 → P2 → P3 → P4 → P5 → P6 → Polish. US1 is the largest effort (29 tasks). Each subsequent story is 5–14 tasks.

---

## Notes

- Each task targets a single function, handler, component, or endpoint — the smallest viable unit
- [P] = different file from other [P] tasks in same wave, no unmet dependencies
- [USn] maps to specific user story for traceability
- Frontend API functions are added per-story, not all upfront (story isolation)
- No placeholder/empty file tasks — files are created when their implementation task runs
- Commit after each task
- All 10 bundled scenarios collectively exercise all four check types and all three difficulty levels
- Embedding model (`all-MiniLM-L6-v2` ONNX) computes embeddings at startup for bundled scenarios and at creation time for generated scenarios
- No ORM — raw `sqlite3` with parameterised queries
- No shell strings — Docker SDK typed calls only
- Service functions are pure business logic; API layer is thin routing + validation only
