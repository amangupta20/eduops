# Implementation Plan: eduops Core Platform

**Branch**: `001-core-platform` | **Date**: 2026-03-04 | **Spec**: [specs/001-core-platform/spec.md](specs/001-core-platform/spec.md)
**Input**: Feature specification from `/specs/001-core-platform/spec.md`

## Summary

Build the eduops core platform: a local-first, interactive Docker learning tool distributed as a Python package (`pip install eduops`). The backend is Python/FastAPI serving a pre-built React (Vite + shadcn/ui) frontend at `localhost:7337`. Users browse or generate structured Docker scenarios, execute them against the host Docker daemon via the Python Docker SDK (no shell strings), receive live log streaming via SSE, get AI coaching through an OpenAI-compatible LLM API (user-supplied key), submit solutions for deterministic checks + AI review, and clean up via label-based resource ownership. Scenario search uses offline embeddings (`all-MiniLM-L6-v2`). Data persists in a local SQLite database with four tables.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript/React (frontend)
**Primary Dependencies**: FastAPI, uvicorn, docker (Python SDK), sentence-transformers[onnx], openai (Python client), httpx, sse-starlette; React, Vite, shadcn/ui, Tailwind CSS
**Storage**: SQLite via Python `sqlite3` (no ORM) at `~/.eduops/eduops.db`
**Testing**: pytest (backend), Vitest (frontend)
**Target Platform**: Linux, macOS, WSL2 (anywhere Docker runs natively)
**Project Type**: CLI + web-service (pip-installable package launching a local web server)
**Performance Goals**: Live log latency <2s (SC-003), coaching response <10s excluding LLM network (SC-005), stale cleanup <15s (SC-008)
**Constraints**: Single concurrent user, no Docker-in-Docker, no shell strings in execution path, offline embeddings only, no ORM, four DB tables only
**Scale/Scope**: Single user, 10 bundled scenarios, ~8 UI screens (catalogue, scenario detail, active session with log+chat panels, config setup)

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| #   | Principle                         | Status   | Notes                                                                                                                                                |
| --- | --------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| I   | FOSS & Local-First                | **PASS** | MIT license, no project-operated backend, user supplies own LLM key, embeddings computed locally                                                     |
| II  | Safe Execution — No Shell Strings | **PASS** | `setup_actions` and `success_checks` are typed parameterised objects; `docker_exec` uses string arrays; unrecognised types rejected before execution |
| III | Deterministic Resource Ownership  | **PASS** | All resources labelled `eduops.session=<uuid>`; cleanup derived from labels in fixed order; stale recovery on startup                                |
| IV  | User-Controlled AI                | **PASS** | User configures key/endpoint in `~/.eduops/config.toml`; AI is reactive only; embeddings are local; no shell history capture                         |
| V   | Fixed v1 Technology Stack         | **PASS** | Python 3.11+/FastAPI, React/Vite/shadcn/ui, SQLite via `sqlite3`, Docker SDK, sentence-transformers, `pip install eduops` → `eduops start`           |
| VI  | Live Log Streaming                | **PASS** | SSE via FastAPI/Starlette streaming responses (`EventSourceResponse`, built on `StreamingResponse`) for `docker logs -f`; no polling fallback        |
| VII | Scope Discipline (v1)             | **PASS** | Docker CLI concepts only; no Compose/Ansible/K8s/auth/gamification/embedded terminal/proactive monitoring                                            |
| ES  | Execution Safety Constraints      | **PASS** | Approved image list enforced, `build_image` for broken scenarios, four check types only, `{{workspace}}` only template variable                      |
| DS  | Development Standards             | **PASS** | No ORM, no migration tooling, four DB tables, bundled scenarios pre-embedded, single active session, `pip install` contract                          |

**Gate result**: **PASS** — no violations detected. Proceeding to Phase 0.

**Post-Design Re-evaluation (Phase 1 complete)**:
All principles re-verified against design artifacts. Key confirmations:

- Pydantic discriminated unions enforce typed actions/checks (Principle II)
- `sse-starlette` `EventSourceResponse` with async generators for SSE (Principle VI)
- `sentence-transformers[onnx]` keeps embeddings local without PyTorch (Principle I, IV)
- `openai` package with `base_url` supports all target providers (Principle IV)
- Four DB tables only, no ORM, raw sqlite3 (Development Standards)
- API contracts expose no scenario internals to the frontend (Principle II, safety)

**Post-design gate result**: **PASS** — no new violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-core-platform/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   └── eduops/
│       ├── __init__.py
│       ├── __main__.py          # `eduops start` entry point
│       ├── cli.py               # CLI argument parsing, first-run setup
│       ├── config.py            # TOML config loading/writing
│       ├── db.py                # SQLite schema init + query helpers
│       ├── models/
│       │   ├── scenario.py      # Scenario schema, validation, typed actions/checks
│       │   └── session.py       # Session lifecycle model
│       ├── services/
│       │   ├── catalogue.py     # Scenario catalogue (load bundled, upsert, search)
│       │   ├── docker_exec.py   # Docker SDK action executor (setup_actions)
│       │   ├── checks.py        # Success check runner (four types)
│       │   ├── cleanup.py       # Label-based cleanup, lifespan shutdown cleanup, stale recovery
│       │   ├── coaching.py      # LLM chat/hint/review integration
│       │   ├── embedding.py     # sentence-transformers embedding + cosine search
│       │   ├── generation.py    # LLM scenario generation + validation + retry
│       │   └── logs.py          # SSE log streaming from docker logs -f
│       ├── api/
│       │   ├── scenarios.py     # GET /scenarios, GET /scenarios/:id, POST /scenarios/search
│       │   ├── sessions.py      # POST /sessions, POST /sessions/:id/submit, DELETE /sessions/:id
│       │   ├── chat.py          # POST /sessions/:id/chat, GET /sessions/:id/chat
│       │   └── logs.py          # GET /sessions/:id/logs (SSE endpoint)
│       ├── prompts/             # LLM system prompt templates
│       └── scenarios/           # Bundled scenario JSON files
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── pyproject.toml
└── README.md

frontend/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── components/
│   │   ├── ui/                  # shadcn/ui components
│   │   ├── ScenarioCatalogue.tsx
│   │   ├── ScenarioCard.tsx
│   │   ├── ActiveSession.tsx
│   │   ├── LogPanel.tsx
│   │   ├── ChatPanel.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── SubmitButton.tsx
│   │   ├── ReviewPanel.tsx
│   │   └── SearchBar.tsx
│   ├── pages/
│   │   ├── Home.tsx             # Catalogue + search
│   │   └── Session.tsx          # Active session view
│   ├── services/
│   │   ├── api.ts               # HTTP client for backend
│   │   └── sse.ts               # SSE client for log streaming
│   └── types/
│       └── index.ts             # TypeScript types mirroring backend models
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── README.md
```

**Structure Decision**: Web application structure with separate `backend/` and `frontend/` directories. The backend is a pip-installable Python package (`eduops`) under `backend/src/eduops/`. The frontend is a Vite/React app that is pre-built and bundled as static files served by FastAPI at `localhost:7337`. This separation keeps build toolchains independent while the distribution model bundles them into a single `pip install`.

## Complexity Tracking

> No constitution violations detected — this section is intentionally empty.
