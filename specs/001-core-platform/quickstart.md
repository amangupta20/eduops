# Quickstart: eduops Development

**Spec**: [specs/001-core-platform/spec.md](specs/001-core-platform/spec.md) | **Date**: 2026-03-04

---

## Prerequisites

- **Python 3.11+** — `python3 --version`
- **Node.js 20+** — `node --version`
- **Docker** — `docker info` (daemon must be running)
- **Git** — `git --version`

---

## Repository Structure

```
eduops/
├── backend/
│   ├── src/eduops/       # Python package source
│   ├── tests/            # pytest tests
│   └── pyproject.toml    # Package config (hatchling)
├── frontend/
│   ├── src/              # React + TypeScript source
│   ├── package.json
│   └── vite.config.ts
├── specs/                # Feature specs and plans
└── README.md
```

---

## Initial Setup

### 1. Clone and branch

```bash
git clone <repo-url> && cd eduops
git checkout 001-core-platform
```

### 2. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The `[dev]` extra includes `pytest`, `ruff`, `mypy`, and other development tools.

### 3. Frontend setup

```bash
cd frontend
npm ci
```

### 4. Verify Docker

```bash
docker info  # Must succeed — Docker daemon must be running
```

---

## Development Workflow

### Backend (FastAPI)

```bash
cd backend
source .venv/bin/activate

# Run the development server (auto-reload)
uvicorn eduops.app:app --reload --port 7337

# Run tests
pytest

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/eduops/
```

### Frontend (React + Vite)

```bash
cd frontend

# Development server with HMR (proxies /api to backend)
npm run dev

# Build for production (output → frontend/dist/)
npm run build

# Lint
npm run lint

# Type check
npm run typecheck
```

### Full stack development

1. Start the backend: `cd backend && uvicorn eduops.app:app --reload --port 7337`
2. Start the frontend dev server: `cd frontend && npm run dev`
3. The Vite dev server proxies `/api` requests to `localhost:7337`
4. Open `http://localhost:5173` (Vite dev server)

### Production-like run

```bash
cd frontend && npm run build      # Build frontend
cd ../backend && eduops start     # Serves everything at localhost:7337
```

---

## First Run (End User)

```bash
pip install eduops
eduops start
# → Interactive setup prompts for LLM provider, API key, model
# → App available at http://localhost:7337
```

---

## Key Configuration

### LLM config: `~/.eduops/config.toml`

```toml
[llm]
provider = "openrouter"
api_key = "sk-or-v1-..."
model = "openai/gpt-4o"

[images]
approved = [
    "nginx:alpine",
    "httpd:alpine",
    "python:3.11-slim",
    "alpine:3",
    "busybox:latest",
    "node:20-alpine",
]
```

### Data paths

| Path                                 | Purpose                           |
| ------------------------------------ | --------------------------------- |
| `~/.eduops/config.toml`              | LLM and image configuration       |
| `~/.eduops/eduops.db`                | SQLite database                   |
| `~/.eduops/workspaces/<session-id>/` | Per-session workspace directories |
| `~/.eduops/models/`                  | Downloaded ONNX embedding model   |

---

## Testing Strategy

| Layer               | Tool                | Scope                                           |
| ------------------- | ------------------- | ----------------------------------------------- |
| Backend unit        | pytest              | Models, validation, DB queries, config loading  |
| Backend integration | pytest + Docker     | Action executor, checks, cleanup, SSE streaming |
| Frontend unit       | Vitest              | Components, services, state logic               |
| Frontend E2E        | Playwright (future) | Full user flows                                 |
| Contract            | pytest              | API endpoint request/response shapes            |

### Running tests

```bash
# Backend (from backend/ with venv activated)
pytest                    # All tests
pytest tests/unit/        # Unit only
pytest tests/integration/ # Requires Docker

# Frontend (from frontend/)
npm test                  # Vitest
```

---

## Build and Package

```bash
# Build frontend
cd frontend && npm run build

# Build Python package (wheel includes frontend/dist as eduops/static/)
cd ../backend && python -m build

# The wheel can be installed anywhere:
pip install dist/eduops-0.1.0-py3-none-any.whl
eduops start
```

---

## Common Tasks

| Task                       | Command                                                                             |
| -------------------------- | ----------------------------------------------------------------------------------- |
| Add a bundled scenario     | Create JSON in `backend/src/eduops/scenarios/`, run `scripts/compute_embeddings.py` |
| Update embeddings          | `python scripts/compute_embeddings.py`                                              |
| Extend approved image list | Add to `~/.eduops/config.toml` under `[images] approved`                            |
| Reset database             | `rm ~/.eduops/eduops.db` — recreated on next start                                  |
| Clean session containers   | `docker ps -a --filter label=eduops.session && docker rm -f <container-id...>`      |
| Clean session networks     | `docker network ls --filter label=eduops.session && docker network rm <network...>` |
| Clean session volumes      | `docker volume ls --filter label=eduops.session && docker volume rm <volume...>`    |
