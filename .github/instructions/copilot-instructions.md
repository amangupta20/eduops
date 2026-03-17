# eduops — AI Agent Instructions

## Current Repository State

This is a **spec-complete, implementation-empty** repo. All design work is done; no source code exists yet. The only existing assets are:

- `specs/001-core-platform/` — all design documents (spec, plan, tasks, data-model, contracts, quickstart, research)
- `.specify/memory/constitution.md` — highest-authority governance document
- `.github/agents/` — SpecKit agent files (Copilot Chat agents)
- `.github/prompts/` — SpecKit prompt files

## What is SpecKit?

This project uses **SpecKit** — a structured spec-driven workflow with AI agents. Key SpecKit agents:

- **`/speckit.implement`** — primary agent for executing tasks from `tasks.md`, phase by phase
- Agents live in `.github/agents/`, prompts in `.github/prompts/`
- The implementation source of truth is `specs/001-core-platform/tasks.md`

## Git Workflow (STRICT)

Every task from `tasks.md` gets its **own feature branch** off `dev`. Never implement more than one task per branch.

Use `feature/<task-or-issue-id>-short-description` for implementation work. SpecKit-created spec branches should use `feature/<feature-id>-short-description` so they still map cleanly to `specs/<feature-id>-short-description`.

```bash
git checkout dev
git checkout -b feature/<task-or-issue-id>-short-description
# implement the task (single function/component/file)
git add <only relevant files>
git commit -m "<type>(<scope>): <what>"  # conventional commits
git push -u origin feature/<task-or-issue-id>-short-description
# open PR → dev
```

**Conventional commit types**: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`  
**Commit after every single task** — never batch multiple tasks in one commit.

**Example**: Task T007 → branch `feature/t007-config-models`, commit `feat(config): add Config, LLMConfig, ImagesConfig Pydantic models`

## Architecture

```
backend/src/eduops/          frontend/src/
├── cli.py                   ├── services/api.ts        # HTTP client
├── config.py                ├── services/sse.ts        # SSE client
├── db.py                    ├── types/index.ts         # mirrors backend models
├── app.py                   ├── components/            # UI components
├── models/                  └── pages/                 # Home, Session
│   ├── scenario.py
│   └── session.py
├── services/
│   ├── catalogue.py         # scenario CRUD + upsert
│   ├── docker_exec.py       # Docker SDK calls (NO shell strings)
│   ├── checks.py            # success_check runners (4 types)
│   ├── cleanup.py           # label-based + expected-name cleanup
│   ├── llm_coaching.py      # chat, hints, review generation
│   ├── embedding.py         # sentence-transformers (local only)
│   ├── generation.py        # LLM scenario generation + validation
│   ├── logs.py              # SSE log streaming from docker logs -f
│   └── session.py           # session lifecycle
├── api/                     # thin routing + validation only
├── prompts/                 # LLM system prompt .txt files
└── scenarios/               # bundled scenario JSON files
```

**Layering rule**: API → Services → Models → DB. No layer skipping. Services hold business logic. API is thin.

## Non-Negotiable Constraints (Constitution)

These override any other consideration. See `.specify/memory/constitution.md` for full rationale.

1. **No shell strings** — `setup_actions` and `success_checks` use typed Pydantic discriminated unions dispatched to Docker SDK calls. `subprocess` and raw shell are banned in the execution path.
2. **No ORM** — raw `sqlite3` only, 4 tables only (`scenarios`, `sessions`, `hint_log`, `chat_log`). Schema changes = delete & recreate the DB file.
3. **No embedding API** — `all-MiniLM-L6-v2` via `sentence-transformers[onnx]` runs locally. No external embedding calls ever.
4. **Fixed stack** — Python 3.11+/FastAPI backend, React/Vite/shadcn/ui frontend, SQLite, Docker SDK, `pip install eduops` → `eduops start`. Suggest no alternatives.
5. **SSE only** — `docker logs -f` streams to frontend via `sse-starlette` `EventSourceResponse`. No polling fallback.
6. **Single active session** — enforced in application logic. Stale sessions must be recovered at startup.
7. **Docker labels** — every resource created by eduops is labelled `eduops.session=<uuid>`. Cleanup is derived from labels + `expected_containers` list (by name).
8. **Blocking checks off event loop** — `run_checks()` is sync and must be called via `await asyncio.to_thread(...)` from the API layer.
9. **User-supplied LLM key** — config at `~/.eduops/config.toml` (TOML). eduops never proxies or stores keys beyond that file.

## Task Execution Order

Tasks are in `specs/001-core-platform/tasks.md`. Execute strictly by phase:

1. **Phase 1 (T001–T006)**: Setup — `pyproject.toml`, Vite scaffold, shadcn/ui, routing skeleton, TS types, test fixtures
2. **Phase 2 (T007–T022)**: Foundational — config, CLI, DB, Pydantic models, FastAPI app shell. **Nothing else starts until this is done.**
3. **Phase 3 (T023–T051)**: US1 MVP — catalogue, Docker executor, SSE logs, bundled scenarios, frontend catalogue + session
4. **Phase 4–8**: US2 → US6 → Polish

Tasks marked `[P]` can run in parallel (separate files, no unfinished deps). Mark tasks `[X]` in `tasks.md` when complete.

## Dev Commands

```bash
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn eduops.app:app --reload --port 7337
pytest
ruff check src/ tests/ && ruff format src/ tests/
mypy src/eduops/

# Frontend
cd frontend && npm ci
npm run dev          # HMR at :5173, proxies /api → :7337
npm run build        # output → frontend/dist/ (bundled into pip package)
```

## Key Design Decisions to Know

- **`{{workspace}}`** is the only template variable in action fields. Resolved to `~/.eduops/workspaces/<session-id>/` before execution.
- **Approved images** (LLM-generated scenarios only): `nginx:alpine`, `httpd:alpine`, `python:3.11-slim`, `alpine:3`, `busybox:latest`, `node:20-alpine`. Broken scenarios use `build_image` + inline Dockerfile, never arbitrary pulls.
- **`schema_json` is never sent to the frontend** — the API exposes only title/description/difficulty/tags/counts to prevent answer leakage.
- **Submit does not end a session** — after review is generated, session stays `active`, containers keep running, re-submission is allowed.
- **"Show Answer" is a dedicated UI button only** — never triggered by message-text analysis.
- **Hint tracking**: backend records consumed hint indices in `hint_log` only after a successful assistant response is persisted. Next unseen hint = lowest index not in `hint_log` for that session.
- **Cleanup order**: expected_containers by name → labelled containers → labelled networks → labelled volumes → workspace dir → DB status update.

## Data Flows

```
Browser → GET /api/scenarios → catalogue.py → SQLite scenarios table
Browser → POST /api/sessions → session.py → docker_exec.py → Docker SDK → labels resources
Browser → GET /api/sessions/:id/logs → logs.py → docker logs -f → SSE stream
Browser → POST /api/sessions/:id/submit → checks.py (thread) → llm_coaching.py → review
Browser → POST /api/sessions/:id/chat → llm_coaching.py → hint_log + chat_log → LLM
Browser → POST /api/scenarios/generate → generation.py → LLM → validate → embedding.py → DB
```

## Spec Reference Files

| Question                              | Read this                                  |
| ------------------------------------- | ------------------------------------------ |
| What to implement and in what order   | `specs/001-core-platform/tasks.md`         |
| Architecture and technology decisions | `specs/001-core-platform/plan.md`          |
| Database schema and state machines    | `specs/001-core-platform/data-model.md`    |
| REST API shapes and error codes       | `specs/001-core-platform/contracts/api.md` |
| Dev setup and commands                | `specs/001-core-platform/quickstart.md`    |
| Core principles and governance        | `.specify/memory/constitution.md`          |
