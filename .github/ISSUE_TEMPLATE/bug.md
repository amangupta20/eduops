---
name: Bug
about: Something broken
labels: bug
---

## What Happened?

## Steps to Reproduce

1.
2.

## Expected Behaviour

## Actual Behaviour

## Environment

- OS:
- Python version:
- Docker version:

```

# EDUOPS Architecture Rules

Read docs/ARCHITECTURE.md and docs/constitution.md before writing any code.
Read the relevant spec file in docs/specs/ before implementing any feature.

## Module Boundaries — Blocking Rules

- eduops/llm/client.py is the ONLY file permitted to make HTTP requests to LLM providers.
  hints.py, chat.py, reviewer.py, generator.py all call client.py — never the API directly.

- eduops/docker/client.py is the ONLY file that instantiates DockerClient.
  All other files in eduops/docker/ import the client from here.

- eduops/session/store.py is the ONLY file that imports sqlite3 or runs SQL.
  session/manager.py calls store functions. Nothing outside session/ touches the DB.

- eduops/config.py is the ONLY file that reads environment variables or config files.
  All other modules receive config values as function arguments.

- eduops/api/ route handlers contain NO business logic.
  They call one module function and return the result. That is all.

- eduops/scenarios/validator.py MUST be called before any setup_actions are passed
  to eduops/docker/executor.py. The executor raises if it receives an unvalidated object.

## Frontend Rules

- React components never call fetch() directly.
  All API calls go through src/api/ functions.
- SSE connection is managed ONLY in src/hooks/useLogStream.ts.
- All shared TypeScript types live in src/types/index.ts only.

## General

- No subprocess calls or shell=True anywhere in the codebase.
- No Docker-in-Docker. No --privileged containers.
- setup_actions are typed objects only. No shell strings ever.

```

Create `.cursor/rules/conventions.mdc`:

```

# EDUOPS Conventions

## Python

- All functions and classes must have docstrings.
- Use type hints on all function signatures.
- Ruff is the formatter and linter. Code must pass ruff check before committing.
- Use mypy for type checking. Resolve type errors, do not suppress them with type: ignore.

## Commits

- Follow Conventional Commits strictly:
  feat: add scenario search endpoint
  fix: resolve SSE disconnect on cleanup
  chore: update ruff config
  docs: add docstring to executor module
- One logical change per commit. Do not bundle unrelated changes.

## Branches

- Always branch off dev: git checkout -b feature/your-feature-name dev
- feature/\* branches target dev only.
- dev targets main only, via PR with owner approval.

## PRs

- Every PR closes a GitHub Issue.
- Every PR checks off the corresponding task in docs/tasks.md.
- Fill the PR template completely. Empty sections are not acceptable.

```

Create `.cursor/rules/forbidden.mdc`:

```

# EDUOPS — Never Do These

- Never use subprocess, os.system, or shell=True for Docker operations.
  Use the Docker SDK exclusively.

- Never hardcode API keys, base URLs, or model names.
  These come from config.py only.

- Never make LLM HTTP calls outside eduops/llm/client.py.

- Never import sqlite3 outside eduops/session/store.py.

- Never import the Docker SDK outside the eduops/docker/ directory.

- Never read os.environ outside eduops/config.py.

- Never write raw shell strings into scenario JSON.
  setup_actions are typed objects only.

- Never push directly to main or dev.

- Never merge a feature branch directly to main.

- Never use Docker-in-Docker or run --privileged containers.

```
