# API Contracts: eduops Core Platform

**Spec**: [specs/001-core-platform/spec.md](specs/001-core-platform/spec.md) | **Date**: 2026-03-04
**Base URL**: `http://localhost:7337/api`

---

## Overview

The eduops backend exposes a REST API consumed by the React frontend. All endpoints are under `/api`. The frontend static files are served at `/` via `StaticFiles(html=True)`.

**Content type**: `application/json` for all request/response bodies except the SSE endpoint.

---

## Scenarios

### `GET /api/scenarios`

List all scenarios in the catalogue.

**Query Parameters**:
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `difficulty` | string | No | | Filter by difficulty: `easy`, `medium`, `hard` |
| `source` | string | No | | Filter by source: `bundled`, `generated` |

**Response** `200 OK`:

```json
{
  "scenarios": [
    {
      "id": "uuid",
      "title": "string",
      "description": "string",
      "difficulty": "easy | medium | hard",
      "tags": ["string"],
      "source": "bundled | generated",
      "created_at": "2026-03-04T12:00:00Z"
    }
  ]
}
```

---

### `GET /api/scenarios/{scenario_id}`

Get full scenario details.

**Response** `200 OK`:

```json
{
  "id": "uuid",
  "title": "string",
  "description": "string",
  "difficulty": "easy | medium | hard",
  "tags": ["string"],
  "source": "bundled | generated",
  "hints_count": 3,
  "success_checks_count": 4,
  "created_at": "2026-03-04T12:00:00Z"
}
```

**Note**: `schema_json` is NOT exposed to the frontend. The frontend never sees setup actions, success check details, or hints. This prevents the user from reading the answers.

**Response** `404 Not Found`:

```json
{ "detail": "Scenario not found" }
```

---

### `POST /api/scenarios/search`

Semantic search over the scenario catalogue.

**Request Body**:

```json
{
  "query": "string — natural language search query"
}
```

**Response** `200 OK`:

```json
{
  "results": [
    {
      "id": "uuid",
      "title": "string",
      "description": "string",
      "difficulty": "easy | medium | hard",
      "tags": ["string"],
      "source": "bundled | generated",
      "score": 0.87,
      "created_at": "2026-03-04T12:00:00Z"
    }
  ]
}
```

Results are ranked by cosine similarity (`score`). Empty or low-relevance results return an empty array.

---

### `POST /api/scenarios/generate`

Generate a new scenario via LLM.

**Request Body**:

```json
{
  "description": "string — what the user wants to practise",
  "difficulty": "easy | medium | hard"
}
```

**Response** `201 Created`:

```json
{
  "id": "uuid",
  "title": "string",
  "description": "string",
  "difficulty": "easy | medium | hard",
  "tags": ["string"],
  "source": "generated",
  "created_at": "2026-03-04T12:00:00Z"
}
```

**Response** `422 Unprocessable Entity` (validation failed after retry):

```json
{
  "detail": "Scenario generation failed validation after retry",
  "errors": ["string — specific validation errors"]
}
```

**Response** `502 Bad Gateway` (LLM unreachable):

```json
{
  "detail": "LLM service unreachable: connection refused"
}
```

---

## Sessions

### `POST /api/sessions`

Start a new scenario session. Creates workspace, executes setup actions, opens log stream.

**Request Body**:

```json
{
  "scenario_id": "uuid"
}
```

**Response** `201 Created`:

```json
{
  "id": "uuid — session ID, also Docker label value",
  "scenario_id": "uuid",
  "status": "active",
  "workspace_path": "/home/user/.eduops/workspaces/session-uuid/",
  "started_at": "2026-03-04T12:00:00Z",
  "scenario": {
    "title": "string",
    "description": "string — task brief shown to the user",
    "difficulty": "easy | medium | hard",
    "tags": ["string"]
  }
}
```

**Response** `409 Conflict` (active session exists):

```json
{
  "detail": "An active session already exists",
  "active_session_id": "uuid"
}
```

**Response** `422 Unprocessable Entity` (setup failed):

```json
{
  "detail": "Scenario setup failed: port 8080 already in use",
  "cleanup_performed": true
}
```

---

### `GET /api/sessions/active`

Get the currently active session, if any.

**Response** `200 OK`:

```json
{
  "id": "uuid",
  "scenario_id": "uuid",
  "status": "active",
  "workspace_path": "/home/user/.eduops/workspaces/session-uuid/",
  "started_at": "2026-03-04T12:00:00Z",
  "scenario": {
    "title": "string",
    "description": "string",
    "difficulty": "easy | medium | hard",
    "tags": ["string"]
  }
}
```

**Response** `404 Not Found`:

```json
{ "detail": "No active session" }
```

---

### `POST /api/sessions/{session_id}/submit`

Submit the current solution for checking and review.

**Response** `200 OK` (checks passed, review generated):

```json
{
  "checks": [
    {
      "check_type": "container_running",
      "check_name": "Container 'web' is running",
      "passed": true,
      "message": "Check passed."
    },
    {
      "check_type": "port_responds",
      "check_name": "Port 8080 responds with 200",
      "passed": true,
      "message": "Check passed."
    }
  ],
  "all_passed": true,
  "review": {
    "what_went_well": ["string"],
    "what_could_improve": ["string"],
    "next_steps": ["string"]
  },
  "session_status": "completed"
}
```

**Response** `200 OK` (some checks failed):

```json
{
  "checks": [
    {
      "check_type": "container_running",
      "check_name": "Container 'web' is running",
      "passed": true,
      "message": "Check passed."
    },
    {
      "check_type": "port_responds",
      "check_name": "Port 8080 responds with 200",
      "passed": false,
      "message": "Expected status 200, got connection refused"
    }
  ],
  "all_passed": false,
  "review": null,
  "session_status": "active"
}
```

**Response** `404 Not Found`:

```json
{ "detail": "Session not found" }
```

**Response** `409 Conflict`:

```json
{ "detail": "Session is not active" }
```

---

### `DELETE /api/sessions/{session_id}`

Abandon/end the active session. Triggers cleanup.

**Response** `200 OK`:

```json
{
  "id": "uuid",
  "status": "abandoned",
  "cleanup_performed": true
}
```

**Response** `404 Not Found`:

```json
{ "detail": "Session not found" }
```

**Response** `409 Conflict`:

```json
{ "detail": "Session is not active" }
```

---

## Chat

### `POST /api/sessions/{session_id}/chat`

Send a message to the AI coach.

**Request Body**:

```json
{
  "message": "string — user's question",
  "show_answer": false
}
```

The `show_answer` field triggers direct-answer mode (switches system prompt). Default `false` for Socratic coaching. Direct-answer mode is only activated via this boolean (set by the UI button) — the backend does not analyse message text for intent.

**Response** `200 OK`:

```json
{
  "role": "assistant",
  "content": "string — AI response (markdown)",
  "created_at": "2026-03-04T12:00:30Z"
}
```

**Response** `404 Not Found`:

```json
{ "detail": "Session not found" }
```

**Response** `409 Conflict`:

```json
{ "detail": "Session is not active" }
```

**Response** `502 Bad Gateway`:

```json
{ "detail": "LLM service error: ..." }
```

---

### `GET /api/sessions/{session_id}/chat`

Get full chat history for a session.

**Response** `200 OK`:

```json
{
  "messages": [
    {
      "role": "user | assistant",
      "content": "string",
      "created_at": "2026-03-04T12:00:00Z"
    }
  ]
}
```

Messages are ordered by `created_at` ascending.

---

## Logs (SSE)

### `GET /api/sessions/{session_id}/logs`

Server-Sent Events stream of live container logs.

**Content-Type**: `text/event-stream`
**Cache-Control**: `no-cache, no-store, must-revalidate`

**SSE Events**:

```
event: log
data: {"container": "web", "line": "172.17.0.1 - - [04/Mar/2026:12:00:00] \"GET / HTTP/1.1\" 200 615", "timestamp": "2026-03-04T12:00:00Z"}
id: 1

event: container_started
data: {"container": "web", "container_id": "abc123"}

event: container_exited
data: {"container": "web", "container_id": "abc123"}

event: dropped
data: {"count": 15, "message": "15 log lines dropped due to backpressure"}

event: session_ended
data: {}
```

**Event Types**:
| Event | Description |
|-------|-------------|
| `log` | A single log line from a session container |
| `container_started` | A new container was detected for this session |
| `container_exited` | A session container has stopped |
| `dropped` | Log lines were dropped due to backpressure |
| `session_ended` | All session containers have exited or session was ended |

**Connection behavior**:

- Opens immediately when session reaches ready state
- Keeps alive via SSE ping comments (`:` every 15s)
- Closes when session ends or client disconnects
- Browser `EventSource` auto-reconnects on drop; server resumes with `tail=100`

---

## Health

### `GET /api/health`

Health check endpoint.

**Response** `200 OK`:

```json
{
  "status": "ok",
  "docker": true,
  "llm_configured": true,
  "active_session": "uuid | null",
  "scenario_count": 10
}
```

**Response fields**:

- `docker`: Whether the Docker daemon is reachable
- `llm_configured`: Whether `~/.eduops/config.toml` has LLM settings
- `active_session`: ID of the active session, or null
- `scenario_count`: Total scenarios in catalogue

---

## Error Response Format

All error responses use a consistent format:

```json
{
  "detail": "string — human-readable error message"
}
```

Additional fields may be present depending on the error type (e.g., `errors` for validation failures, `active_session_id` for conflicts).

**HTTP Status Codes Used**:
| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Resource created |
| `404` | Resource not found |
| `409` | Conflict (active session exists, session not active) |
| `422` | Validation error |
| `500` | Internal server error |
| `502` | Upstream service error (LLM unreachable) |
