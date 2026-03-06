# Feature Specification: eduops Core Platform

**Feature Branch**: `001-core-platform`
**Created**: 2026-03-04
**Status**: Draft
**Input**: User description: "eduops core platform — local-first Docker learning platform with AI coaching"

## Clarifications

### Session 2026-03-04

- Q: What configuration file format and path should eduops use for LLM settings? → A: TOML at `~/.eduops/config.toml`, with an interactive first-run setup prompt (provider → key → model) when config is missing.
- Q: When LLM-generated scenario validation fails, should the platform retry automatically? → A: One automatic retry with the validation error fed back to the LLM; if the second attempt also fails, show the error to the user and let them rephrase.
- Q: How long should success checks wait before declaring failure? → A: 30-second timeout with 2-second polling interval per check.
- Q: Should the coaching chat avoid giving direct answers? → A: Strictly Socratic by default (system prompt forbids direct answers), but the user can explicitly request the answer via a dedicated "Show Answer" button in the UI. No message-text intent detection — direct-answer mode is triggered only by the button to prevent accidental answer reveals.
- Q: How many bundled scenarios should ship with v1? → A: 10 bundled scenarios covering core Docker topics, exercising all four success check types.

## User Scenarios & Testing _(mandatory)_

### User Story 1 — Browse and Start a Bundled Scenario (Priority: P1)

A learner installs eduops, runs it, opens the browser, and browses the bundled scenario catalogue. They pick a scenario about Docker port bindings, read the task description, select it, and are handed control. The platform sets up the required Docker environment automatically. The learner sees a live log panel streaming container output and a chat panel where they can ask questions. They work in their own terminal, completing the task using real Docker commands.

**Why this priority**: Without the ability to browse, start, and execute a bundled scenario end-to-end, no other feature delivers value. This is the irreducible MVP — scenario catalogue, scenario setup, live logs, and the user working in their own terminal.

**Independent Test**: Install the package, run `eduops start`, open `localhost:7337`, select a bundled scenario, verify Docker containers are created with correct labels, confirm the log panel streams live output, and confirm the user can work in their own terminal against the running containers.

**Acceptance Scenarios**:

1. **Given** eduops is installed and Docker is running, **When** the user runs `eduops start` and opens `localhost:7337`, **Then** the UI loads and displays the scenario catalogue with all bundled scenarios.
2. **Given** the scenario catalogue is displayed, **When** the user selects a scenario, **Then** the platform creates the workspace directory, executes all setup actions (pulling images, creating networks/volumes, running containers), labels every created resource with `eduops.session=<uuid>`, and transitions to the ready state.
3. **Given** a scenario is in the ready state, **When** the user views the UI, **Then** the live log panel streams `docker logs -f` output from all session-labelled containers in real time via SSE.
4. **Given** a scenario is active, **When** the user runs Docker commands in their own terminal against the scenario containers, **Then** the containers respond normally and log output appears in the UI log panel.

---

### User Story 2 — Submit a Solution and Receive AI Review (Priority: P2)

While working on an active scenario, the learner completes the task and clicks "Submit" in the UI. The platform runs deterministic success checks (container running, port responds, etc.) and reports which passed and which failed. If checks pass, the platform collects Docker inspection data and container logs, sends them along with scenario context to the user-configured LLM, and displays an AI-generated review in the chat panel. The review covers what the user did well, what could be improved, and what to try next. The scenario is marked complete and cleanup runs automatically.

**Why this priority**: Submission and review close the learning loop. Without this, the platform is just a scenario launcher — the coaching value comes from feedback on what the user actually did.

**Independent Test**: With an active scenario running, complete the task correctly in a terminal, click Submit, verify checks run and pass, verify the LLM is called with inspection data, verify a review appears in chat, and verify cleanup removes all session-labelled resources.

**Acceptance Scenarios**:

1. **Given** a scenario is active and the user has completed the task, **When** the user clicks Submit, **Then** the platform runs all `success_checks` defined in the scenario and displays the results (pass/fail for each check).
2. **Given** all success checks pass, **When** the review is generated, **Then** the platform collects `docker inspect` output and container logs, sends them with `review_context` to the configured LLM, and displays the review in the chat panel.
3. **Given** one or more success checks fail, **When** the results are displayed, **Then** the user sees which specific checks failed with enough detail to understand what's wrong, and the scenario remains active (not auto-completed).
4. **Given** a scenario is marked complete after a successful review, **When** cleanup runs, **Then** all session-labelled containers are stopped and removed, session networks and volumes are removed, the workspace directory is deleted, and the session is marked closed.

---

### User Story 3 — Ask for Help During a Scenario (Priority: P3)

While working on an active scenario, the learner gets stuck and types a question into the chat panel, such as "My container starts but the port isn't accessible from the host." The platform sends the question along with the scenario context and hint history to the LLM. The LLM responds with guidance — nudging the user towards the solution without giving it away directly. The platform tracks which hints have been shown so it never repeats the same hint.

**Why this priority**: The coaching interaction during a scenario is a core differentiator, but the platform still delivers value (scenario + review) without it. This builds on top of the submission flow.

**Independent Test**: With an active scenario, type a question in the chat panel, verify the LLM is called with scenario context, verify the response appears in chat, ask a follow-up, and verify hint history prevents repeated hints.

**Acceptance Scenarios**:

1. **Given** a scenario is active and the user types a question in the chat panel, **When** the message is sent, **Then** the platform forwards the question along with scenario description, current hint history, and session context to the configured LLM, and displays the response in the chat panel.
2. **Given** the scenario includes structured hints, **When** the user asks for help and a hint is surfaced, **Then** the hint is recorded in the hint log so the same hint is never shown again in this session.
3. **Given** a chat history exists for the session, **When** the user reloads the browser, **Then** the full chat history for the active session is restored from persistence.

---

### User Story 4 — Generate a Custom Scenario via Chat (Priority: P4)

The learner can't find a scenario that matches what they want to practise. They open the chat and describe what they want: "I want to practise debugging a container that exits immediately because of a bad entrypoint." They select a difficulty level. The platform sends the description to the LLM with the scenario JSON schema and the approved image list as constraints. The LLM returns a structured scenario. The platform validates the scenario (checking for only approved action types, only approved check types, only approved images), persists it with a locally computed embedding, and offers it for immediate start.

**Why this priority**: On-demand scenario generation is the core differentiator — it turns a fixed set of bundled exercises into an infinite learning surface tailored to what the user actually wants to practise. Without it, eduops is just another static tutorial collection.

**Independent Test**: In the chat, describe a desired scenario and select a difficulty, verify the LLM is called with the correct schema and constraints, verify the returned scenario passes validation, verify it appears in the catalogue with an embedding, and verify it can be started.

**Acceptance Scenarios**:

1. **Given** the user describes a desired scenario in the chat and selects a difficulty, **When** the request is sent, **Then** the platform prompts the LLM with the scenario JSON schema, the approved image list, and the four allowed check types, and receives a structured scenario JSON response.
2. **Given** the LLM returns a scenario, **When** the platform validates it, **Then** any scenario with unrecognised action types, unapproved check types, or images outside the approved list is rejected with a clear error message to the user.
3. **Given** a generated scenario passes validation, **When** it is persisted, **Then** it is saved to the scenario catalogue with a locally computed embedding, marked as `source: generated`, and immediately available for selection and start.

---

### User Story 5 — Search Scenarios by Natural Language (Priority: P5)

Instead of browsing the catalogue, the learner types a natural-language query into the scenario search bar — for example, "practice bind mounts." The platform computes an embedding of the query locally and compares it against pre-computed embeddings for all scenarios. The most relevant scenarios are returned, ranked by similarity.

**Why this priority**: Semantic search improves discoverability as the catalogue grows (especially with generated scenarios), but the platform works with manual browsing alone.

**Independent Test**: With bundled scenarios loaded, type a query like "volumes," verify results are ranked by semantic similarity and not just substring match, verify no network calls are made for the embedding.

**Acceptance Scenarios**:

1. **Given** the scenario catalogue is populated with bundled scenarios (each with pre-computed embeddings), **When** the user types a natural-language query into the search bar, **Then** the platform computes the query embedding locally and returns scenarios ranked by cosine similarity.
2. **Given** no scenarios closely match the query, **When** results are displayed, **Then** the user sees an empty or low-relevance result set and is not shown unrelated scenarios.

---

### User Story 6 — Abandon a Session and Clean Up (Priority: P6)

The learner decides to stop working on a scenario mid-way. They click "End session" in the UI. All Docker resources created for the session are stopped and removed, the workspace is cleaned up, and the session is marked as abandoned. The user can then start a new scenario.

**Why this priority**: Clean session lifecycle management prevents resource leaks and is necessary for a usable product, but it's a supporting flow — not a primary learning journey.

**Independent Test**: Start a scenario, click "End session," verify all session-labelled Docker resources are removed, verify the workspace directory is deleted, and verify a new scenario can be started immediately.

**Acceptance Scenarios**:

1. **Given** a scenario is active, **When** the user clicks "End session," **Then** all containers labelled `eduops.session=<uuid>` are stopped and removed, all session networks and volumes are removed, the workspace directory is deleted, and the session status is set to `abandoned`.
2. **Given** no active session exists, **When** the user opens the UI, **Then** the "End session" control is not shown, and the user can browse and start a new scenario.
3. **Given** the eduops process was killed without clean shutdown (stale session), **When** the user runs `eduops start`, **Then** the platform detects the orphaned session, cleans up all resources found via label-based Docker queries, and allows the user to proceed.

---

### Edge Cases

- What happens when Docker is not running or not installed when `eduops start` is executed? The platform must detect this and show a clear error message before attempting any scenario operations.
- What happens when the user-configured LLM endpoint is unreachable or returns an error? Scenario browsing, selection, and execution (all local operations) must still work. Only chat, hint, review, and generation features should degrade, with a clear error message.
- What happens when `~/.eduops/config.toml` exists but contains an invalid or expired API key? The platform must attempt the LLM call, surface the provider's error message clearly, and allow the user to re-run setup or edit the config file.
- What happens when a setup action fails mid-sequence (e.g., image pull timeout, port already in use)? The platform must clean up any resources created by prior actions in the sequence and report the specific failure to the user.
- What happens when the user starts a scenario while another session's containers are still running from a crashed process? Stale session recovery must run first, cleaning up orphaned resources before allowing a new session.
- What happens when the LLM generates a scenario with an unapproved image or unrecognised action/check type? The platform retries once with the validation error fed back to the LLM. If the second attempt also fails, the scenario is rejected, never executed, and the user sees the specific validation errors with the option to rephrase.
- What happens when `success_checks` fail because the user's work is partially correct? Each check reports independently so the user knows exactly which checks passed and which failed.
- What happens when the host port requested by a scenario is already in use? The setup action must fail clearly and not leave orphaned containers.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST install via `pip install eduops` and start via `eduops start`, launching a server that serves the UI at `localhost:7337`.
- **FR-002**: System MUST detect whether Docker is installed and the Docker daemon is running at startup, and display a clear error if either condition is not met.
- **FR-003**: System MUST populate the scenario catalogue from bundled scenario files on first start and on every subsequent start (upserting, not duplicating).
- **FR-004**: The package MUST ship with 10 bundled scenarios covering the core v1 Docker topics (running containers, port bindings, bind mounts, named volumes, Dockerfile basics, image building, container debugging, environment variables, networking two containers, and multi-step workflows). Collectively, the 10 scenarios MUST exercise all four success check types (`container_running`, `port_responds`, `docker_exec`, `file_in_workspace`) and all three difficulty levels.
- **FR-005**: System MUST display a browsable scenario catalogue in the UI, showing title, description, difficulty, and tags for each scenario.
- **FR-006**: System MUST support semantic search over the scenario catalogue using locally computed embeddings, with no external API calls for embedding computation.
- **FR-007**: System MUST execute scenario setup by translating typed `setup_actions` objects directly to Docker SDK calls — no shell strings, no `subprocess`, no arbitrary command execution.
- **FR-008**: System MUST label every Docker resource it creates (containers, networks, volumes) with `eduops.session=<session-uuid>`.
- **FR-009**: System MUST create a workspace directory at `~/.eduops/workspaces/<session-id>/` for each session, populate it with scenario-defined `workspace_files`, and resolve the `{{workspace}}` template variable in all action fields before execution. No other template variables are permitted in v1.
- **FR-010**: System MUST stream live container logs from all session-labelled containers to the frontend via Server-Sent Events.
- **FR-011**: System MUST provide a chat panel in the UI where the user can ask questions during an active scenario and receive LLM-generated coaching responses. The LLM MUST be system-prompted to use Socratic guidance by default — asking guiding questions and pointing to relevant commands/concepts without revealing the direct solution.
- **FR-012**: The UI MUST provide an explicit "Show Answer" button that, when activated, instructs the LLM to reveal the direct solution. Direct-answer mode MUST only be triggered by the explicit UI button — not by message-text analysis — to prevent accidental answer reveals when the user is still working through the problem.
- **FR-013**: System MUST track shown hints per session and never repeat the same hint within a session.
- **FR-014**: System MUST run deterministic `success_checks` when the user submits a solution, reporting pass/fail per check with enough detail for the user to understand what failed. Each check MUST use a 30-second timeout with a 2-second polling interval before declaring failure.
- **FR-015**: System MUST collect `docker inspect` output and container logs after successful checks and send them, along with `review_context`, to the configured LLM to generate a review.
- **FR-016**: System MUST persist the AI review with the session record once generated.
- **FR-017**: System MUST support LLM-based scenario generation from a user-provided description and difficulty level, constrained to the approved image list and the four allowed check types.
- **FR-018**: System MUST validate all LLM-generated scenarios against the typed schema before persisting or executing — rejecting any scenario with unrecognised action types, unapproved check types, or unapproved images.
- **FR-019**: When an LLM-generated scenario fails validation, the system MUST automatically retry once by sending the validation errors back to the LLM for correction. If the second attempt also fails validation, the system MUST display the specific validation errors to the user and allow them to rephrase their request.
- **FR-020**: System MUST compute and store an embedding for each newly generated scenario at creation time.
- **FR-021**: System MUST run cleanup in deterministic order — stop containers → remove containers → remove networks → remove volumes → delete workspace directory → mark session closed in SQLite — on normal completion, explicit abandon, and process termination (`SIGINT`/`SIGTERM`).
- **FR-022**: System MUST detect stale sessions on startup and clean up orphaned Docker resources via label-based queries before allowing new scenario starts.
- **FR-023**: System MUST enforce single active session — the user cannot start a new scenario while another session is active or stale.
- **FR-024**: System MUST accept LLM configuration (API key, endpoint, model) from a TOML configuration file at `~/.eduops/config.toml`, and MUST NOT proxy, store, or transmit the API key anywhere beyond the configured endpoint.
- **FR-025**: System MUST work with any LLM provider that implements the OpenAI chat completions API specification.
- **FR-026**: On `eduops start`, if `~/.eduops/config.toml` does not exist or lacks LLM configuration, the CLI MUST present an interactive setup prompt that walks the user through selecting a provider, entering an API key, and selecting a model, then writes the result to `~/.eduops/config.toml`.
- **FR-027**: System MUST persist all chat messages (user and assistant) per session so the UI can restore conversation history on page reload.
- **FR-028**: System MUST only accept the four defined success check types: `container_running`, `port_responds`, `docker_exec`, `file_in_workspace`. Any other type MUST be rejected before execution.
- **FR-029**: System MUST constrain LLM-generated scenarios to the approved base image list: `nginx:alpine`, `httpd:alpine`, `python:3.11-slim`, `alpine:3`, `busybox:latest`, `node:20-alpine`. The list MUST be extensible by the user via configuration.
- **FR-030**: Scenarios requiring broken or exotic images MUST use a `build_image` action with an approved base image and introduce faults via inline Dockerfile content — never by pulling an arbitrary external image.
- **FR-031**: `docker_exec` commands in success checks MUST be passed as a string array. No shell interpolation or shell string execution is permitted.

### Key Entities

- **Scenario**: A structured learning exercise with a title, description, difficulty, tags, workspace files, setup actions, success checks, hints, and review context. Can be bundled (shipped with the package) or generated (created by the LLM at runtime). Each scenario has a pre-computed embedding for semantic search.
- **Session**: A single attempt at a scenario by the user. Tracks status (active, completed, abandoned), links to the scenario, owns a workspace directory, and carries the eventual AI review. Identified by a UUID that is also used as the Docker resource label value.
- **Hint Log Entry**: A record that a specific hint (by index) was shown in a specific session, preventing repeats.
- **Chat Message**: A single user or assistant message within a session, persisted for history restoration and context building.
- **Setup Action**: A typed, parameterised object representing a single Docker SDK operation (pull image, build image, create network, create volume, run container). No shell strings.
- **Success Check**: A typed, parameterised object representing a single verification step (container running, port responds, docker exec, file in workspace). Four types only.

## Assumptions

- Users have a working Docker installation with the Docker daemon running and accessible via the default socket.
- Users are comfortable with a terminal and can run `pip install` commands (or use `pipx`).
- Users will configure their own LLM API key and endpoint via an interactive first-run prompt or by editing `~/.eduops/config.toml` directly. Coaching, chat, review, and scenario generation features will not function without a configured LLM.
- The approved base image list is sufficient for v1 Docker learning scenarios. Users needing additional images can extend the list via config.
- A single concurrent user is expected (local tool, one browser tab). No multi-user concurrency requirements.
- Network connectivity is available for Docker image pulls and LLM API calls, but no other network access is required by the platform itself.
- Pre-computed embeddings shipped with bundled scenarios are generated using the same model version (`all-MiniLM-L6-v2`) that the platform uses at runtime.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: A new user can go from `pip install eduops` to completing their first bundled scenario in under 30 minutes, including LLM configuration.
- **SC-002**: 100% of bundled scenarios execute their setup actions, run their success checks, and complete cleanup without errors on Linux, macOS, and WSL2.
- **SC-003**: The live log panel displays container output within 2 seconds of it being written inside a container.
- **SC-004**: Semantic search returns the most relevant bundled scenario as the top result for at least 80% of natural-language queries that describe a bundled scenario's topic.
- **SC-005**: The AI coaching response appears in the chat panel within 10 seconds of the user sending a question (network latency to LLM provider excluded).
- **SC-006**: Scenario cleanup removes 100% of session-labelled Docker resources (containers, networks, volumes) and the workspace directory — verified by post-cleanup Docker queries returning zero results for the session label.
- **SC-007**: LLM-generated scenarios that violate the approved image list or use unapproved action/check types are rejected 100% of the time before any Docker operation is performed.
- **SC-008**: Stale session recovery at startup correctly identifies and cleans up orphaned resources from a previous crashed session within 15 seconds.
