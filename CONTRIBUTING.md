# Contributing to EDUOPS

## Before You Start

Read `docs/constitution.md` and `docs/ARCHITECTURE.md` fully.
Read the spec file for the feature area you're working on in `docs/specs/`.

## Branch Model

main ← stable, owner approval required to merge
└── dev ← integration, 1 teammate approval required  
 └── feature/your-task-name ← your working branch

Never push directly to main or dev.

## Workflow for Every Task

1. Pick an unassigned Issue from "This Sprint" on the project board
2. Assign it to yourself and move it to "In Progress"
3. Branch off dev:
   git checkout -b feature/your-task-name dev
4. Write code. Commit often with Conventional Commits.
5. Open a PR targeting dev. Fill the template completely.
6. CodeRabbit reviews automatically — fix anything flagged as blocking.
7. One teammate reviews and approves.
8. Merge. Check off the task in docs/tasks.md in the merge commit.

## Commit Messages

feat: add SSE streaming endpoint  
fix: resolve cleanup not running on SIGTERM  
docs: add docstring to validator module  
chore: update ruff config

## AI-Generated Code

If AI generated code you do not fully understand, understand it before opening the PR.
You are responsible for the code, not the AI.

## Module Rules

- All LLM calls go through eduops/llm/client.py only
- All Docker SDK usage stays inside eduops/docker/
- All SQLite access stays inside eduops/session/store.py
- API route handlers contain no business logic
