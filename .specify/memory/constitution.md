<!--
  Sync Impact Report
  ──────────────────
  Version change: 1.0.0 → 1.0.1 (PATCH — wording clarification)
  Modified principles:
    - I. FOSS & Local-First: clarified LLM API is a required
      external dependency, not a "cloud service operated by the
      project"; removed misleading "no cloud services" framing.
  Added sections: none
  Removed sections: none
  Templates requiring updates:
    - .specify/templates/plan-template.md        ✅ no changes needed
    - .specify/templates/spec-template.md         ✅ no changes needed
    - .specify/templates/tasks-template.md        ✅ no changes needed
  Follow-up TODOs: none
-->

# eduops Constitution

## Core Principles

### I. FOSS & Local-First

eduops is open-source software with no proprietary dependencies in the
core path. The platform MUST run on the user's machine. There MUST be
no project-operated remote backend, no telemetry, and no phone-home
behaviour of any kind.

- The full source is publicly licensed (MIT).
- No feature may require a cloud service operated by the project.
- eduops MUST NOT operate, bundle, or proxy an LLM service. The user
  configures their own API key and endpoint in a local config file.
  An external LLM API is a **required runtime dependency** — scenario
  generation, coaching, and review do not function without it.
- Apart from the user-configured LLM endpoint, no network calls are
  made. Scenario search, embeddings, and all other platform logic run
  entirely locally.

**Rationale:** The platform itself is local-first, but it is not
offline-capable — current local LLMs are not reliable enough for the
complex tasks eduops requires (structured scenario generation,
contextual coaching, solution review). Acknowledging the LLM API as
an explicit external dependency keeps the architecture honest while
ensuring the project never becomes the middleman for that dependency.

### II. Safe Execution — No Shell Strings (NON-NEGOTIABLE)

Neither `setup_actions` nor `success_checks` MUST ever contain
arbitrary shell strings. Both MUST use typed, parameterised objects
that map directly to Docker SDK or HTTP calls. This constraint applies
equally to LLM-generated and human-authored scenarios.

- An action with an unrecognised `action` type MUST be rejected
  before execution.
- A check with a `type` outside the four approved types
  (`container_running`, `port_responds`, `docker_exec`,
  `file_in_workspace`) MUST be rejected at validation time.
- `docker_exec` commands MUST be passed as a string array — no shell
  interpolation.

**Rationale:** Allowing raw shell strings in a system that accepts
LLM-generated content is an unacceptable injection surface. Typed
objects make the attack space enumerable and auditable.

### III. Deterministic Resource Ownership

Every Docker resource created by eduops MUST be labelled
`eduops.session=<uuid>`. Cleanup MUST be derived from these labels,
not declared in scenario schemas.

- Teardown order: stop containers → remove containers → remove
  networks → remove volumes → delete workspace directory → mark
  session closed in SQLite.
- Cleanup runs on: normal completion, explicit abandon, process
  termination (`SIGINT`/`SIGTERM`), and stale session recovery at
  startup.
- No Docker-in-Docker. Scenario containers are managed via the host
  Docker socket through the Python Docker SDK.

**Rationale:** Label-based ownership makes cleanup deterministic and
guarantees eduops never touches resources the user created outside
the platform.

### IV. User-Controlled AI

The user MUST supply their own LLM API key and endpoint. eduops MUST
NOT hold, proxy, or store API keys beyond the local configuration
file.

- Any provider that speaks the OpenAI chat completions spec MUST work.
- The AI MUST be reactive: it responds when asked, hints when
  requested, and reviews when the user submits. It MUST NOT
  proactively monitor the user's terminal or interrupt work.
- Scenario search MUST use a locally computed embedding model
  (`all-MiniLM-L6-v2` via `sentence-transformers`). No embedding API
  calls are permitted.
- Shell history MUST NOT be captured. Review evidence comes from
  Docker's own inspection APIs only.

**Rationale:** A learning tool that phones home with keystrokes or
requires a managed AI subscription defeats the local-first promise
and introduces a privacy liability.

### V. Fixed v1 Technology Stack (NON-NEGOTIABLE)

The following technology choices are load-bearing and MUST NOT be
changed or substituted during v1 development:

| Layer        | Choice                                        |
| ------------ | --------------------------------------------- |
| Backend      | Python 3.11+ with FastAPI                     |
| Frontend     | React (Vite) with shadcn/ui                   |
| Storage      | SQLite via Python `sqlite3` (no ORM)          |
| Docker       | Python Docker SDK (`docker` package)          |
| Embeddings   | `sentence-transformers` (`all-MiniLM-L6-v2`)  |
| Distribution | `pip install eduops` → `eduops start`         |
| Runtime dep  | Docker (host daemon). No VMs, no Podman shim. |

- Suggesting Go, Node, or Rust for the backend is out of scope.
- The FastAPI server serves the pre-built React frontend as static
  files on `localhost:7337`.
- eduops runs natively on the host — it does NOT run inside Docker.

**Rationale:** The Docker SDK, embedding model, and LLM client
libraries all have mature Python implementations. Constraining the
stack eliminates bikeshedding and keeps the 31-day timeline feasible.

### VI. Live Log Streaming (NON-NEGOTIABLE)

The backend MUST stream `docker logs -f` output to the frontend via
Server-Sent Events (SSE) using FastAPI's `StreamingResponse`. This is
a hard requirement — no polling fallback is acceptable.

- The SSE stream opens as soon as the scenario reaches ready state.
- The stream covers all containers labelled with the active session
  UUID.

**Rationale:** Real-time log visibility is what separates "AI coach
beside you" from "read the docs yourself." A polling fallback adds
latency that breaks the coaching UX.

### VII. Scope Discipline (v1)

v1 covers Docker CLI concepts only: `docker run`, Dockerfiles,
volumes, networks, and port bindings. The following are explicitly
out of scope and MUST NOT be implemented or designed for in v1:

- Docker Compose, Ansible, Kubernetes, Docker Swarm.
- User accounts, authentication, cloud sync, leaderboards.
- An embedded terminal in the UI.
- Proactive AI monitoring or shell history capture.
- Metrics, streaks, XP systems, or gamification.
- Proactive scenario difficulty adaptation.
- A community scenario server or submission backend.

**Rationale:** Protecting build time is the top priority. Every
out-of-scope item is explicitly deferred to v2+ so that "maybe we
should also..." conversations have a clear answer: not now.

## Execution Safety Constraints

These constraints supplement principle II and MUST be enforced in both
the scenario validation layer and the LLM generation prompt.

- **Approved image list:** LLM-generated scenarios MUST use only
  approved base images for `run_container` and `build_image`:
  `nginx:alpine`, `httpd:alpine`, `python:3.11-slim`, `alpine:3`,
  `busybox:latest`, `node:20-alpine`. The list is user-extensible
  via config.
- **Broken scenarios use build_image:** Scenarios requiring broken or
  exotic images MUST use a `build_image` action with an approved base
  and introduce faults via inline Dockerfile content — never by
  pulling an arbitrary external image.
- **Four check types only:** `container_running`, `port_responds`,
  `docker_exec`, `file_in_workspace`. Any other type MUST be rejected
  at validation time.
- **Template variable substitution:** The `{{workspace}}` variable
  MUST be resolved before action execution. No other template
  variables are permitted in v1.

## Development Standards

- **No ORM.** Use Python's `sqlite3` module directly. Queries are
  simple enough that an ORM adds overhead without benefit.
- **No migration tooling in v1.** If the schema changes between
  versions, the SQLite file is deleted and recreated.
- **Four database tables only:** `scenarios`, `sessions`, `hint_log`,
  `chat_log`. Do not add tables without amending this constitution.
- **Bundled scenario format:** Scenarios are JSON files conforming to
  the schema defined in the base document (appendix). Bundled
  scenarios ship pre-embedded; generated scenarios are embedded at
  creation time.
- **Single active session:** Only one scenario session may be active
  at a time. Stale sessions MUST be resolved before a new scenario
  can start.
- **Installation contract:** `pip install eduops` installs the
  package. `eduops start` launches the server. Docker MUST be
  installed and running. No other runtime dependencies.

## Governance

This constitution is the highest-authority document for the eduops
project. All implementation decisions, code reviews, and architecture
discussions MUST comply with the principles defined here.

- **Amendment procedure:** Any change to a principle or constraint
  requires updating this file, incrementing the version, and
  recording the change in the Sync Impact Report comment block at the
  top of this file.
- **Versioning policy:** MAJOR for principle removals or
  redefinitions, MINOR for new principles or materially expanded
  guidance, PATCH for wording or clarification fixes.
- **Compliance review:** Every PR and design document MUST be
  verified against this constitution before merge. The "Constitution
  Check" section in plan documents serves as the gate.
- **Scope changes:** Adding items to the v1 scope (principle VII)
  requires a MAJOR version bump and explicit justification.
- **Conflict resolution:** If a spec or plan contradicts this
  constitution, the constitution wins. Update the spec, not the
  constitution — unless an amendment is formally proposed.

**Version**: 1.0.1 | **Ratified**: 2026-03-04 | **Last Amended**: 2026-03-04
