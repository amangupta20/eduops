# Phase 0 Research: eduops Core Platform

**Spec**: [specs/001-core-platform/spec.md](specs/001-core-platform/spec.md) | **Date**: 2026-03-04
**Scope**: All technical decisions for the core platform implementation

---

# Area 1: SSE Log Streaming (FastAPI + Docker SDK)

**Scope**: Live container log streaming via SSE (FR-010, SC-003)

---

## Topic 1: SSE Pattern in FastAPI

### Decision

Use the `sse-starlette` package (`EventSourceResponse`) with an async generator — not bare `StreamingResponse`.

### Rationale

FastAPI's built-in `StreamingResponse` can serve SSE by setting `media_type="text/event-stream"`, but it provides none of the SSE protocol machinery. You must manually format `data:`, `id:`, `event:`, and `retry:` fields, handle keepalive pings yourself, and manage client disconnect detection. `sse-starlette` (`EventSourceResponse`) wraps `StreamingResponse` and adds:

1. **Automatic SSE formatting** — yield a `dict` or `ServerSentEvent` and the library serialises it to spec-compliant wire format.
2. **Built-in keepalive pings** — configurable `ping` interval (seconds) that sends invisible SSE comments (`:`), preventing proxies/load balancers from killing idle connections.
3. **`send_timeout`** — detects stalled sends (client gone but TCP hasn't RST'd yet), preventing the generator from hanging indefinitely.
4. **`asyncio.CancelledError` propagation** — when the client disconnects, Starlette cancels the response task. `EventSourceResponse` ensures this propagates into the async generator's `finally` block so cleanup runs reliably.
5. **`X-Accel-Buffering: no`** header support — critical when behind Nginx.

The async generator pattern is idiomatic:

```python
from sse_starlette import EventSourceResponse

async def log_stream(request: Request, session_id: str):
    try:
        async for event in multiplex_logs(session_id):
            if await request.is_disconnected():
                break
            yield {"data": event.data, "event": event.type, "id": event.id}
    except asyncio.CancelledError:
        # cleanup runs in finally
        raise
    finally:
        await cleanup_log_followers(session_id)

@app.get("/sessions/{session_id}/logs")
async def stream_logs(request: Request, session_id: str):
    return EventSourceResponse(
        log_stream(request, session_id),
        ping=15,
        send_timeout=30,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Accel-Buffering": "no",
        },
    )
```

### Alternatives Considered

| Alternative                                                | Why Rejected                                                                                                                                                                                                                              |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bare `StreamingResponse` with `text/event-stream`          | No ping, no send_timeout, no automatic SSE formatting. Every project ends up reimplementing what `sse-starlette` already provides.                                                                                                        |
| WebSockets                                                 | Overkill for unidirectional server→client log streaming. SSE has native browser reconnect (`EventSource`), simpler error model, and the spec requires no bidirectional framing. The plan explicitly mandates SSE (Constitution check VI). |
| Long polling                                               | Explicitly excluded by spec ("no polling fallback"). Higher latency, more complex client state machine.                                                                                                                                   |
| Third-party SSE libs (`aiohttp-sse`, `django-eventstream`) | Wrong framework. `sse-starlette` is the canonical choice for Starlette/FastAPI and is actively maintained.                                                                                                                                |

---

## Topic 2: Multiplexing Docker Logs from Multiple Containers

### Decision

Use an `asyncio.Queue` as a fan-in point. Each container gets a dedicated log-following task that pushes tagged lines onto the shared queue. The SSE async generator reads from the queue and yields events.

### Rationale

A session may have N containers (identified by `eduops.session=<uuid>`). Each container's `container.logs(stream=True, follow=True)` returns a **blocking** iterator. These must be run concurrently and their output merged into a single ordered SSE stream.

**Architecture**:

```
Container A  ──→  [Thread A] ──→  asyncio.Queue  ──→  async generator ──→  SSE
Container B  ──→  [Thread B] ──↗                       (yields events)
Container C  ──→  [Thread C] ──↗
```

1. **Discover containers**: `client.containers.list(filters={"label": f"eduops.session={session_id}"})` returns all running containers for the session.
2. **Watch for new containers**: A separate task monitors `client.events(filters={"label": f"eduops.session={session_id}", "type": "container", "event": ["start", "die"]}, decode=True)` to detect containers starting or stopping during the session.
3. **Fan-in queue**: One `asyncio.Queue(maxsize=1000)` per SSE connection. Each log-follower thread calls `queue.put_nowait()` (or `loop.call_soon_threadsafe(queue.put_nowait, item)` since it's called from a thread). The async generator does `event = await asyncio.wait_for(queue.get(), timeout=30)` — the timeout triggers a keepalive/check cycle.
4. **Event format**: Each queued item is a dataclass like `LogEvent(container_name: str, container_id: str, line: str, timestamp: datetime)`. The SSE event includes the container name as the `event` field so the frontend can colour/filter per container.

**Container lifecycle during streaming**:

- **New container starts**: The Docker events watcher detects `start`, spawns a new log-follower thread, adds it to the tracked set.
- **Container stops/dies**: The `logs(follow=True)` iterator terminates naturally when the container exits. The thread puts a `ContainerExited(container_id)` sentinel on the queue and exits. The events watcher also sees `die` as confirmation.
- **All containers gone**: The generator can yield a final `event: session_ended` and return, closing the SSE connection.

### Alternatives Considered

| Alternative                                    | Why Rejected                                                                                                                                                                      |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `asyncio.merge` / async iteration merge        | The Docker SDK's `logs(stream=True)` is synchronous/blocking — cannot be used directly in an async merge. Would still need threads underneath, adding complexity without benefit. |
| Single thread iterating containers round-robin | Blocking on one container's `logs()` iterator starves others. Would need non-blocking reads which the SDK doesn't support natively.                                               |
| One SSE connection per container               | Violates the "single SSE stream" requirement. Multiplies browser connections (6 per domain limit). Makes frontend ordering/interleaving harder.                                   |
| `subprocess.Popen("docker logs -f ...")`       | Violates the "no shell strings" constitution constraint. The Docker SDK is the mandated interface.                                                                                |

---

## Topic 3: Client Disconnect Cleanup

### Decision

Use `asyncio.CancelledError` propagation in the async generator's `finally` block to trigger cleanup of all log-following threads. Additionally, check `request.is_disconnected()` as a belt-and-suspenders guard.

### Rationale

When a client closes the SSE connection (browser tab closed, `EventSource.close()`, network drop), Starlette's ASGI server detects the `http.disconnect` message and cancels the response body iteration task. This raises `asyncio.CancelledError` inside the async generator. The `finally` block is the **only** reliable place to perform cleanup.

**Cleanup sequence**:

```python
async def log_stream(request, session_id):
    queue = asyncio.Queue(maxsize=1000)
    cancel_event = threading.Event()  # signals threads to stop
    follower_threads: list[threading.Thread] = []
    event_watcher_task: asyncio.Task | None = None

    try:
        # 1. Start log followers for existing containers
        containers = docker_client.containers.list(
            filters={"label": f"eduops.session={session_id}"}
        )
        for container in containers:
            t = _start_log_follower(container, queue, cancel_event)
            follower_threads.append(t)

        # 2. Start Docker events watcher (asyncio task)
        event_watcher_task = asyncio.create_task(
            _watch_container_events(session_id, queue, cancel_event, follower_threads)
        )

        # 3. Yield from queue
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
            except asyncio.TimeoutError:
                continue  # sse-starlette ping handles keepalive
            if event is _SENTINEL_DONE:
                break
            yield {"data": json.dumps(event.to_dict()), "event": "log", "id": event.id}

    except asyncio.CancelledError:
        raise  # re-raise after finally runs
    finally:
        # 4. Signal all threads to stop
        cancel_event.set()
        # 5. Cancel the event watcher
        if event_watcher_task:
            event_watcher_task.cancel()
        # 6. Join threads with timeout (don't block forever)
        for t in follower_threads:
            t.join(timeout=2.0)
```

**Key details**:

- `threading.Event` (`cancel_event`) is set in `finally` to signal all blocking follower threads to stop reading. Each thread checks `cancel_event.is_set()` between log line reads.
- Threads must also handle the Docker SDK raising an exception when the container is removed while `logs()` is blocking — wrap in `try/except (docker.errors.APIError, requests.exceptions.ConnectionError)`.
- `t.join(timeout=2.0)` prevents cleanup from hanging if a thread is stuck in a blocking Docker API call. Daemon threads are a fallback for truly stuck threads.
- `sse-starlette`'s `send_timeout=30` provides a secondary safety net — if `CancelledError` somehow doesn't fire (e.g., client disconnect not detected at TCP level), the send will time out.

### Alternatives Considered

| Alternative                                        | Why Rejected                                                                                                                                                                               |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Rely solely on `request.is_disconnected()` polling | Not reliable as the sole mechanism — requires an `await` point to check, and the Docker log threads are blocking outside the event loop. Must be paired with `CancelledError`.             |
| Daemon threads only (no explicit join)             | Daemon threads are killed at process exit but not at connection close. Log followers would keep running, consuming Docker API connections and memory, until the server process shuts down. |
| `atexit` handler                                   | Only runs at process termination, not per-connection. Useless for per-SSE-connection cleanup.                                                                                              |
| Reference counting / garbage collection            | Non-deterministic. The generator object may not be collected for an arbitrary period after disconnect.                                                                                     |

---

## Topic 4: Threading vs. Asyncio for Docker SDK Log Following

### Decision

Use **threads** (`threading.Thread` or `concurrent.futures.ThreadPoolExecutor`) for the blocking `container.logs(stream=True, follow=True)` calls. Bridge to asyncio via `loop.call_soon_threadsafe()` or `asyncio.Queue` with `run_in_executor` for the put.

### Rationale

The Python Docker SDK (`docker` package, backed by `requests`) is fully synchronous. `container.logs(stream=True, follow=True)` returns a blocking generator that calls `requests` under the hood and blocks on `socket.recv()`. There is no async Docker SDK with production-quality maintenance.

**Why not `asyncio.to_thread` / `run_in_executor` directly on the whole logs iterator?**

You can do:

```python
async def follow_one_container(container, queue):
    def _blocking():
        for line in container.logs(stream=True, follow=True, timestamps=True):
            queue.put_nowait(LogEvent(..., line=line.decode()))
    await asyncio.to_thread(_blocking)
```

This works and is the simplest approach — `asyncio.to_thread` runs the blocking function in the default `ThreadPoolExecutor`. However, explicit `threading.Thread` with a `cancel_event` is preferred because:

1. **Cancellation control**: `asyncio.to_thread` doesn't propagate cancellation into the blocking function. If the async task is cancelled, the thread keeps running until the next `socket.recv()` returns (which may be never for a quiet container). With explicit threads, the `cancel_event` can be checked inside the loop, and `container.close()` can be called to unblock the socket.
2. **Thread naming**: Named threads (`Thread(name=f"log-{container.short_id}")`) make debugging and log diagnosis much easier.
3. **Bounded concurrency**: A dedicated set of follower threads is easier to reason about than sharing the default executor with other `run_in_executor` calls in the application.

**Pattern**:

```python
def _follow_container_logs(
    container: docker.models.containers.Container,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
    cancel_event: threading.Event,
):
    """Runs in a dedicated thread. Follows container logs and pushes to async queue."""
    try:
        log_stream = container.logs(
            stream=True, follow=True, timestamps=True, tail=100
        )
        for chunk in log_stream:
            if cancel_event.is_set():
                break
            line = chunk.decode("utf-8", errors="replace").rstrip()
            event = LogEvent(
                container_name=container.name,
                container_id=container.short_id,
                line=line,
            )
            loop.call_soon_threadsafe(queue.put_nowait, event)
    except (docker.errors.APIError, requests.exceptions.ConnectionError):
        pass  # container removed or Docker daemon restarted
    finally:
        # Signal this follower is done
        loop.call_soon_threadsafe(
            queue.put_nowait,
            ContainerExited(container_id=container.short_id),
        )
```

**Backpressure**: The `asyncio.Queue(maxsize=1000)` provides backpressure. If the SSE consumer falls behind, `queue.put_nowait()` raises `QueueFull`. The thread should catch this and either drop the line (with a warning log) or block briefly. Dropping is preferred since logs are ephemeral and the client can't process them anyway if it's behind. A more sophisticated approach: switch to `queue.put()` with a timeout inside `asyncio.to_thread`, but this complicates the thread code. For v1, drop + warn is sufficient.

### Alternatives Considered

| Alternative                                                                  | Why Rejected                                                                                                                                                                                                                          |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `aiodocker` (async Docker client)                                            | Third-party, less mature than the official `docker` SDK. Has had stability issues and gaps in API coverage. The spec mandates the `docker` package. Adding a second Docker client library creates confusion.                          |
| `asyncio.to_thread` without cancellation                                     | Simpler code but no way to stop the blocking iterator on disconnect. Threads linger until the container produces output or exits. Acceptable for low container counts, but the explicit thread + cancel_event pattern is more robust. |
| `subprocess` + `asyncio.create_subprocess_exec("docker", "logs", "-f", ...)` | Async-native, but violates the "no shell strings / subprocess" constraint. Also bypasses the SDK's connection pooling and authentication handling.                                                                                    |
| Single-threaded with `select()` on Docker socket                             | Possible via the low-level API (`client.api.logs()` returns a response with a `socket` attribute), but extremely fragile, undocumented, and breaks the SDK abstraction. Not worth the complexity.                                     |

---

## Topic 5: Gotchas and Known Issues

### 5a. Starlette StreamingResponse and `asyncio.CancelledError` Timing

**Issue**: In older Starlette versions (< 0.30), `CancelledError` was sometimes swallowed during response body iteration, preventing generator cleanup. Fixed in Starlette 0.30+ / FastAPI 0.100+.

**Mitigation**: Pin `starlette>=0.30` (via FastAPI version). Also check `request.is_disconnected()` inside the generator loop as a redundant safety check.

### 5b. Docker SDK `logs()` Blocking Forever on Quiet Containers

**Issue**: `container.logs(stream=True, follow=True)` blocks on `socket.recv()` and will not return until the container writes output or exits. If the client disconnects and the `cancel_event` is set, the thread won't notice until the next chunk arrives.

**Mitigation**: After setting `cancel_event`, also close the underlying response socket:

```python
# In cleanup
cancel_event.set()
try:
    log_stream.close()  # log_stream is the generator from container.logs()
except Exception:
    pass
```

Each follower thread must store its `log_stream` reference so cleanup can call `.close()` on it. This forces the blocking `recv()` to raise an exception, unblocking the thread.

### 5c. `queue.put_nowait()` from Thread Requires `loop.call_soon_threadsafe()`

**Issue**: `asyncio.Queue.put_nowait()` is not thread-safe. Calling it directly from a thread can corrupt the queue's internal state.

**Mitigation**: Always use `loop.call_soon_threadsafe(queue.put_nowait, item)`. Get the loop reference via `asyncio.get_running_loop()` before spawning threads.

### 5d. Docker SDK `events()` is Also Blocking

**Issue**: `client.events(decode=True, filters=...)` is a blocking iterator, same as `logs()`. It cannot be used directly in an async function.

**Mitigation**: Run the events watcher in its own thread, same pattern as log followers. Alternatively, use `asyncio.to_thread` since there's only one events watcher per session and cancellation is less critical (it can be signalled via `cancel_event`).

### 5e. SSE Reconnection and `Last-Event-ID`

**Issue**: The browser's `EventSource` API automatically reconnects on connection drop and sends the `Last-Event-ID` header. If the server doesn't handle this, the client gets duplicate or missing logs.

**Mitigation**: For v1, accept that log reconnection restarts the stream with `tail=100` (recent context). Set `retry: 3000` in the SSE events so reconnection isn't too aggressive. Do **not** attempt to implement a full replay buffer in v1 — it adds significant complexity (sequence numbering, bounded buffer, ID-based seeking) for a local-only single-user tool. Document this as a v2 enhancement.

### 5f. Browser `EventSource` 6-Connection Limit (HTTP/1.1)

**Issue**: Browsers limit concurrent connections to the same origin to ~6 under HTTP/1.1. If the app opens multiple SSE connections (e.g., one per panel), it can exhaust this budget.

**Mitigation**: The design already mandates a single multiplexed SSE connection per session. This is correct. Additionally, uvicorn supports HTTP/2 via `hypercorn` if needed, but for local-only use with a single user this is unnecessary.

### 5g. Large Log Volume / Backpressure

**Issue**: A container producing thousands of lines per second (e.g., verbose debug logging) can overwhelm the queue, the SSE connection, and the browser.

**Mitigation**:

1. Queue `maxsize=1000` provides server-side backpressure.
2. `tail=100` on initial attach limits the initial burst.
3. `send_timeout=30` on `EventSourceResponse` kills stalled connections.
4. For v1, if queue is full, drop the oldest line and increment a dropped counter. Periodically yield a `event: dropped` SSE event with the count so the frontend can show "X lines dropped."
5. As a future enhancement, consider client-requested rate limiting or log level filtering.

### 5h. Docker SDK Thread Safety

**Issue**: The `docker.DockerClient` instance is thread-safe for read operations (it uses `requests.Session` which is thread-safe for separate calls). However, creating a new client per thread is wasteful.

**Mitigation**: Share a single `docker.DockerClient` instance across all threads. Each call to `container.logs()` creates its own HTTP connection from the connection pool.

---

## Summary of Decisions

| #   | Topic                | Decision                                                                                                                          |
| --- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 1   | SSE pattern          | `sse-starlette` `EventSourceResponse` + async generator                                                                           |
| 2   | Multiplexing         | `asyncio.Queue` fan-in, one thread per container, Docker events watcher for lifecycle                                             |
| 3   | Disconnect cleanup   | `finally` block on `CancelledError`, `threading.Event` to signal threads, `join(timeout=2)`                                       |
| 4   | Threading vs asyncio | Explicit `threading.Thread` per container, bridged to asyncio via `loop.call_soon_threadsafe()`                                   |
| 5   | Key gotchas          | Close log_stream on cleanup, use `call_soon_threadsafe`, skip replay in v1, single SSE connection, bounded queue for backpressure |

## Dependencies to Add

| Package         | Version | Purpose                                                                   |
| --------------- | ------- | ------------------------------------------------------------------------- |
| `sse-starlette` | `>=2.0` | `EventSourceResponse` with ping, send_timeout, proper disconnect handling |

_(Already required: `fastapi`, `uvicorn`, `docker`)_

---

---

# Area 2: Python Packaging & Distribution

**Spec**: [specs/001-core-platform/spec.md](specs/001-core-platform/spec.md) | **Date**: 2026-03-04
**Scope**: Packaging `eduops` as a pip-installable Python package that bundles a FastAPI backend, pre-built React frontend, scenario data, and pre-computed embeddings.

---

## Topic 1: Package Structure — Including Static Frontend Assets

### Decision

Use `src` layout (`backend/src/eduops/`) with a `static/` sub-package inside the `eduops` package directory. Include the pre-built React output via hatchling's `force-include` to map the frontend build output into the package at build time. Declare static files using hatchling's `artifacts` or `force-include` — **not** `data_files`.

Target layout inside the installed package:

```
eduops/
├── __init__.py
├── __main__.py
├── static/           # Pre-built React output (index.html, assets/)
│   ├── index.html
│   └── assets/
│       ├── index-xxxxx.js
│       └── index-xxxxx.css
├── scenarios/        # Bundled JSON scenario files
│   ├── 001-port-binding.json
│   └── ...
├── data/             # Pre-computed embeddings
│   └── embeddings.bin
└── ...
```

### Rationale

There are two mechanisms for including non-Python files in a pip package:

1. **`package_data`** (setuptools) / in-package inclusion (hatchling): Files placed under a Python package directory (i.e., alongside `__init__.py`) are included in the wheel. This is the standard, reliable method. Files end up installed inside `site-packages/eduops/`, co-located with the code. This makes them discoverable via `importlib.resources` or `__file__`-relative paths.

2. **`data_files`**: Installs files to _absolute paths_ outside the package (e.g., `/usr/share/`). This is fragile, platform-dependent, does not work in virtual environments as expected, and is effectively deprecated for application packaging. The Python Packaging Authority explicitly advises against it for most use cases.

By placing the built React output directly inside `src/eduops/static/`, it becomes regular package data — included automatically by hatchling (which includes all files under the package directory by default unless excluded). No special `package_data` glob is needed with hatchling.

For the build workflow (copying frontend build output into the package tree), hatchling's `[tool.hatch.build.targets.wheel.force-include]` provides a clean declarative mapping:

```toml
[tool.hatch.build.targets.wheel.force-include]
"../frontend/dist" = "eduops/static"
```

This maps the Vite build output (`frontend/dist/`) to `eduops/static/` inside the wheel, regardless of the source tree layout.

### Alternatives Considered

| Alternative                           | Why Rejected                                                                                                                                                                                               |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data_files` in `pyproject.toml`      | Installs to system-level paths, not inside the package. Breaks in virtualenvs. Not relocatable. Effectively deprecated for application use.                                                                |
| `package_data` with setuptools globs  | Works but requires explicit glob patterns (`*.html`, `*.js`, `*.css`, `**/*`) that must be maintained as file types change. Hatchling includes everything by default, eliminating this maintenance burden. |
| Separate `eduops-frontend` package    | Over-engineered for a single-app distribution. Adds version-sync complexity for no benefit. The frontend is not independently useful.                                                                      |
| Download frontend assets at first run | Requires network access at install/first-run time, violates local-first principle, adds error states (download failures, checksum mismatches), poor UX.                                                    |

---

## Topic 2: Build Workflow — Frontend Build Automation

### Decision

Make `npm run build` a **manual pre-build step** (documented in `CONTRIBUTING.md` and enforced by CI). Do **not** automate it via PEP 517 build hooks.

The developer/CI workflow is:

```bash
cd frontend && npm ci && npm run build   # produces frontend/dist/
cd ../backend && python -m build         # hatchling picks up frontend/dist via force-include
```

### Rationale

A PEP 517 build hook (e.g., a custom hatchling `BuildHookInterface` that runs `subprocess.run(["npm", "run", "build"])`) is technically possible but introduces significant problems:

1. **Node.js as a build-time dependency**: Anyone running `pip install .` from source or `python -m build` would need Node.js + npm installed. This is not a Python packaging norm and breaks `pip install` from sdist for users who only have Python.
2. **Sdist contamination**: The sdist would need to include the entire `frontend/` source tree (TypeScript, `node_modules` lock, Vite config). This bloats the sdist and couples Python packaging to the JS toolchain.
3. **Non-reproducibility**: The npm build depends on `node_modules` state, Node.js version, etc. Build hooks run in isolated environments (PEP 517) where `node_modules` may not exist.
4. **Complexity**: A custom build hook that runs npm, captures errors, and handles cross-platform Node paths adds fragile code to the build system for little gain.

The standard pattern for projects with mixed Python/JS is:

- **Development**: Manual `npm run build` (or `npm run dev` for HMR).
- **CI/CD**: A build step that runs `npm ci && npm run build` before `python -m build`.
- **PyPI release**: Upload a wheel that already contains the pre-built frontend (built by CI). End users `pip install eduops` and get the wheel — no Node.js needed.

This is the same pattern used by JupyterLab, Streamlit, Gradio, and other Python projects that bundle frontend assets.

### Alternatives Considered

| Alternative                                                   | Why Rejected                                                                                                                                                                                          |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Custom hatchling `BuildHookInterface` running `npm run build` | Requires Node.js at build time. Breaks `pip install .` from sdist for Python-only users. Adds fragile subprocess code to the build system.                                                            |
| `setuptools` `cmdclass` override (custom `build_py`)          | Legacy pattern, same Node.js requirement problem. Also, we chose hatchling as the build backend.                                                                                                      |
| Include `frontend/dist/` in the git repo                      | Pollutes VCS with build artifacts. Merge conflicts on binary files. But acceptable as a pragmatic fallback for very small teams — we choose the CI approach instead.                                  |
| Makefile / `justfile` orchestrating both builds               | Good for local dev but doesn't solve the PEP 517 isolation problem. Complementary to (not a replacement for) the manual approach. A `Makefile` or `justfile` is recommended as a convenience wrapper. |

---

## Topic 3: CLI Entry Point — `eduops` Command

### Decision

Define the CLI via `[project.scripts]` in `pyproject.toml`, pointing to a `cli:main` function:

```toml
[project.scripts]
eduops = "eduops.cli:main"
```

Where `eduops.cli:main` parses arguments (primarily `eduops start`), runs first-run config setup if needed, and launches uvicorn.

### Rationale

`[project.scripts]` is the standard PEP 621 mechanism for console entry points. When `pip install eduops` runs, pip creates a wrapper script in the environment's `bin/` (or `Scripts\` on Windows) that calls `eduops.cli:main()`. This is:

- **Cross-platform**: pip generates the correct wrapper for the OS.
- **Virtual-environment aware**: The script is placed in the venv's `bin/`, not system-wide.
- **No `__main__.py` dependency**: The entry point works regardless of how the package is invoked. However, providing `__main__.py` as well enables `python -m eduops` as a fallback, which is useful for debugging.

The `main()` function should:

1. Parse CLI args (`start`, `--port`, `--host`, `--version`, etc.) — use `argparse` (stdlib) since the CLI is minimal.
2. On `eduops start`: check for `~/.eduops/config.toml`, run interactive first-run setup if missing.
3. Launch `uvicorn.run("eduops.app:app", host=host, port=7337)`.

Supporting `python -m eduops` as well (via `__main__.py` that calls `main()`) is a free addition and useful for environments where the script entry point isn't on `PATH`.

### Alternatives Considered

| Alternative                                        | Why Rejected                                                                                                                                            |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[project.gui-scripts]`                            | Wrong category — `eduops` is a CLI tool, not a GUI app. `gui-scripts` suppresses the console window on Windows.                                         |
| `click` or `typer` for CLI parsing                 | Additional dependency for a CLI with ~3 commands. `argparse` from stdlib is sufficient. If the CLI grows significantly, `click` could be adopted later. |
| `entry_points` console_scripts (setuptools legacy) | `[project.scripts]` is the PEP 621 equivalent and is build-backend agnostic. Same result, better standard.                                              |
| Shell wrapper script checked into repo             | Not cross-platform. Not installed by pip. Fragile.                                                                                                      |

---

## Topic 4: Heavy Dependencies — `sentence-transformers` and PyTorch

### Decision

Use `sentence-transformers` with the **ONNX backend** (`sentence-transformers[onnx]`) and a pre-exported ONNX model file. This replaces PyTorch (~2 GB) with `onnxruntime` (~50–200 MB) as the inference engine, while keeping the `sentence-transformers` high-level API.

Declare it as:

```toml
[project]
dependencies = [
  "sentence-transformers[onnx]",
  # ... other deps
]
```

Ship a pre-exported `all-MiniLM-L6-v2` ONNX model bundled inside the package (or downloaded on first use to `~/.eduops/models/`).

### Rationale

The `sentence-transformers` library requires PyTorch by default. PyTorch is ~2 GB and dominates the install size. For `eduops`, embeddings are used only for:

1. Computing query embeddings for scenario search (a few per session).
2. Computing embeddings for newly generated scenarios (one at a time).

This is CPU-only, low-throughput inference — PyTorch's GPU training capabilities are entirely unused.

**`sentence-transformers` ONNX backend** (available since v3.0+):

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2", backend="onnx")
embeddings = model.encode(["query text"])
```

This uses `onnxruntime` under the hood. If the ONNX model file is already present (pre-exported), no PyTorch is needed at runtime. The `sentence-transformers[onnx]` extra installs `onnxruntime` and `optimum` instead of pulling PyTorch.

**Size comparison**:

| Approach                                                      | Approximate install size |
| ------------------------------------------------------------- | ------------------------ |
| `sentence-transformers` (default, PyTorch)                    | ~2.5 GB                  |
| `sentence-transformers[onnx]` (ONNX Runtime)                  | ~300–500 MB              |
| Raw `onnxruntime` + `tokenizers` (no `sentence-transformers`) | ~100–200 MB              |

**Pre-exported ONNX model**: The `all-MiniLM-L6-v2` model is ~80 MB as ONNX. It can be:

- **Bundled in the package**: Adds 80 MB to the wheel. Acceptable for a tool with already-heavy dependencies.
- **Downloaded on first use**: Keeps the wheel small but requires network access and adds first-run latency. Given the spec's local-first principle, bundling is simpler and more reliable.

**Decision on model bundling**: Download on first use to `~/.eduops/models/` with a progress indicator. Reason: the 80 MB model + onnxruntime already have inherent download costs via pip, and bundling it in the wheel makes the PyPI package unnecessarily large. The model download is a one-time cost with a clear UX (progress bar + status message during first run).

### Alternatives Considered

| Alternative                                                                | Why Rejected                                                                                                                                                                                                                                                                                                                                                        |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Accept PyTorch as a dependency                                             | 2+ GB install for CPU-only embedding of short strings. Unacceptable UX for a CLI tool. Many users would abandon install before completion.                                                                                                                                                                                                                          |
| Raw `onnxruntime` + `tokenizers` (no `sentence-transformers`)              | Eliminates `sentence-transformers` entirely (~50% lighter). Requires manual tokenization, mean pooling, and normalization code. The code is ~30 lines but must be validated for correctness against the original model. **This is a viable v2 optimisation** if the `sentence-transformers` dependency proves problematic. For v1, the high-level API reduces risk. |
| `fastembed` (Qdrant's lightweight embedding library)                       | Uses ONNX Runtime internally, ~100 MB lighter than `sentence-transformers[onnx]`. But it's a less-maintained third-party library with a smaller community. If `sentence-transformers[onnx]` works well, there's no reason to switch. Worth revisiting if dependency size is still a concern in v2.                                                                  |
| Make embeddings an optional feature with `[project.optional-dependencies]` | Semantic search is a core feature (User Story 5), not optional. Making it optional would mean `pip install eduops` gives a broken search experience by default. The user would need to know to run `pip install eduops[search]`. Poor UX.                                                                                                                           |
| Pre-compute all embeddings, skip runtime model entirely                    | Works for bundled scenarios (already planned — embeddings ship pre-computed). Breaks for generated scenarios (User Story 4) and user search queries (User Story 5), which require runtime embedding computation.                                                                                                                                                    |

---

## Topic 5: Static File Serving — `importlib.resources` vs `__file__`

### Decision

Use `importlib.resources` (Python 3.9+ `importlib.resources.files()` API) to locate the `static/` directory, then pass the resolved path to FastAPI's `StaticFiles(directory=...)`. For the SPA fallback (serving `index.html` for client-side routes), use `StaticFiles(html=True)`.

```python
from importlib.resources import files

static_dir = files("eduops").joinpath("static")

# For FastAPI — need a real filesystem path
# importlib.resources.as_file() provides a context manager for this
from importlib.resources import as_file

static_ref = files("eduops").joinpath("static")
# In practice, for installed packages, this is already a real path
# as_file() is needed for zip-imported packages (rare)

app.mount("/", StaticFiles(directory=str(static_ref), html=True), name="spa")
```

### Rationale

There are two standard approaches to locate package data at runtime:

**`importlib.resources.files()` (recommended)**:

- Part of the stdlib since Python 3.9 (with `importlib_resources` backport).
- Works correctly with zip-imported packages, frozen apps, and any `importlib` loader.
- Returns a `Traversable` path-like object. For packages installed normally (not zipped), this resolves to a real filesystem path.
- `files("eduops").joinpath("static")` gives the path to the `static/` subdirectory.
- The Python Packaging Authority recommends this over `__file__`-based approaches.

**`__file__`-relative paths (legacy)**:

```python
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
```

- Works for normally-installed packages but fails for zip imports.
- `__file__` may not be defined in all execution contexts (e.g., frozen executables, some importers).
- Simpler and more widely understood, but technically less correct.

**Practical consideration for `eduops`**: Since `eduops` is a pip-installed package that launches a web server (not a library imported by others), it will always be installed as a regular directory in `site-packages/`. Zip imports are not a realistic concern. Both approaches would work identically. However, `importlib.resources` is the recommended modern approach and costs nothing extra.

**FastAPI `StaticFiles` with `html=True`**: When `html=True` is set, `StaticFiles` automatically serves `index.html` for directory requests and returns `index.html` as a fallback for missing paths — exactly the behaviour needed for a React SPA with client-side routing. This eliminates the need for a custom catch-all route.

**FastAPI `StaticFiles` with `packages` parameter**: Starlette's `StaticFiles` also supports a `packages` parameter that can serve files from an installed package:

```python
StaticFiles(packages=[("eduops", "static")], html=True)
```

This uses `importlib.resources` internally, providing the cleanest one-liner. However, inspection of the Starlette source shows it calls `importlib.resources.files(package).joinpath(subdir)` — identical to the manual approach. The `packages` parameter is cleaner but less transparent.

### Decision Refinement

Use `StaticFiles(packages=[("eduops", "static")], html=True)` as the primary approach — it is the most concise and leverages Starlette's built-in package resource resolution. Fall back to the explicit `importlib.resources.files()` + `directory=` approach only if debugging shows issues.

### Alternatives Considered

| Alternative                                        | Why Rejected                                                                                                                                                       |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `__file__`-relative `os.path.join`                 | Works but deprecated pattern. `importlib.resources` is the recommended replacement from the packaging authority.                                                   |
| `pkg_resources.resource_filename()` (setuptools)   | Deprecated. `pkg_resources` has known performance issues (slow import) and is being replaced by `importlib.resources`.                                             |
| `pkgutil.get_data()`                               | Returns file contents as bytes, not a path. Cannot be passed to `StaticFiles(directory=...)`. Designed for reading individual files, not serving a directory tree. |
| Symlink from a known path to the installed package | Fragile, platform-dependent, requires post-install step.                                                                                                           |
| Serve from `~/.eduops/static/` (copy on first run) | Unnecessary indirection. The files are already in the installed package. Copying them wastes disk and adds a failure mode.                                         |

---

## Topic 6: Bundling Pre-Computed Data (Embeddings + Scenario JSON)

### Decision

Bundle scenario JSON files and pre-computed embedding vectors as regular package data files inside the `eduops` package tree:

```
eduops/
├── scenarios/
│   ├── 001-port-binding.json
│   ├── 002-volume-mounts.json
│   └── ...  (10 files)
└── data/
    └── scenario_embeddings.json
```

**Embedding format**: A single JSON file mapping scenario IDs to base64-encoded 384-dimensional float32 vectors. Each embedding is 384 × 4 = 1,536 bytes raw, ~2,048 bytes base64-encoded. For 10 scenarios: ~20 KB total. Trivially small.

Alternative binary format (for scale): A single `.bin` file with a fixed-size header followed by concatenated raw float32 vectors, plus an index JSON mapping scenario IDs to byte offsets. But for 10 scenarios this is over-engineering — JSON with base64 is sufficient and human-inspectable.

### Rationale

**Scenario JSON files**:

- Each scenario is a structured JSON file matching the scenario schema (defined in the spec).
- They are read at startup by the catalogue service, validated, and loaded into SQLite.
- Placing them under `eduops/scenarios/` makes them regular package data, included in the wheel automatically.
- Access at runtime via `importlib.resources.files("eduops").joinpath("scenarios")`.

**Pre-computed embeddings**:

- Each bundled scenario needs a 384-dim float32 embedding vector (from `all-MiniLM-L6-v2`).
- These are computed once at development time (via a dev script) and committed to the repo.
- Avoids requiring the embedding model to be loaded just to seed bundled scenarios on first run.
- For 10 scenarios, total data is ~15 KB (raw float32) — negligible.

**Format choice**: JSON with base64-encoded vectors is chosen for v1 because:

1. **Human-readable**: Developers can inspect the mapping.
2. **Diffable**: Changes to scenario embeddings show up in git diffs.
3. **Simple**: No custom binary parser needed. Python's `base64.b64decode()` + `struct.unpack()` or `numpy.frombuffer()` decodes each vector.
4. **Sufficient scale**: 10 scenarios × 2 KB per embedding = 20 KB. Even 1,000 scenarios would be only 2 MB.

**Pre-computation workflow**: A development script (`scripts/compute_embeddings.py`) loads the embedding model, reads all JSON files from `scenarios/`, computes embeddings, and writes `data/scenario_embeddings.json`. This runs as part of the development workflow (not at install time, not at runtime for bundled scenarios).

### Alternatives Considered

| Alternative                                  | Why Rejected                                                                                                                                                                                                                                        |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Embed vectors inside each scenario JSON file | Pollutes the scenario schema with a packaging concern. Makes scenario files harder to read/edit. Couples the scenario format to the embedding model version.                                                                                        |
| NumPy `.npy` / `.npz` file                   | Adds a NumPy dependency just for loading embeddings. For 10 vectors, `struct.unpack` or a list of floats in JSON is simpler. NumPy may be pulled in transitively by `sentence-transformers` anyway, but we shouldn't depend on it for data loading. |
| SQLite database shipped as package data      | Over-engineered. The DB is created at runtime in `~/.eduops/`. Shipping a pre-populated DB creates schema coupling between build time and runtime.                                                                                                  |
| Raw `.bin` file with custom header           | Better for 1000+ scenarios (mmap-friendly, zero-copy). Over-engineering for 10.                                                                                                                                                                     |
| Pickle file                                  | Security risk (arbitrary code execution on load). Fragile across Python versions. Universally discouraged for data interchange.                                                                                                                     |
| Parquet / Arrow                              | Heavyweight dependency for tabular data. Wrong abstraction for a vector-per-scenario mapping.                                                                                                                                                       |
| Compute embeddings at first run              | Requires the embedding model to be loaded just to seed 10 known vectors. Adds 5–10 seconds to first launch. The pre-computation approach eliminates this entirely.                                                                                  |

---

## Summary of Decisions

| #   | Topic               | Decision                                                                                                                                                  |
| --- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Package structure   | `src` layout, pre-built React output in `eduops/static/` via hatchling `force-include`. No `data_files`.                                                  |
| 2   | Build workflow      | Manual `npm run build` before `python -m build`. No PEP 517 build hooks for frontend. CI enforces the sequence.                                           |
| 3   | CLI entry point     | `[project.scripts] eduops = "eduops.cli:main"` + `__main__.py` for `python -m eduops` fallback. `argparse` for parsing.                                   |
| 4   | Heavy dependencies  | `sentence-transformers[onnx]` with ONNX Runtime instead of PyTorch. Pre-exported ONNX model downloaded on first use. ~300–500 MB vs ~2.5 GB.              |
| 5   | Static file serving | `StaticFiles(packages=[("eduops", "static")], html=True)` — uses `importlib.resources` internally. SPA fallback via `html=True`.                          |
| 6   | Bundled data        | Scenario JSON in `eduops/scenarios/`, embeddings in `eduops/data/scenario_embeddings.json` (base64-encoded float32). Pre-computed at dev time via script. |

## Resulting `pyproject.toml` Skeleton

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "eduops"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "docker>=7.0",
    "sentence-transformers[onnx]",
    "openai>=1.0",
    "httpx>=0.27",
    "sse-starlette>=2.0",
]

[project.scripts]
eduops = "eduops.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/eduops"]

[tool.hatch.build.targets.wheel.force-include]
"../frontend/dist" = "eduops/static"
```

## Dependencies to Add

| Package                       | Version      | Purpose                                                                                  |
| ----------------------------- | ------------ | ---------------------------------------------------------------------------------------- |
| `hatchling`                   | `>=1.26`     | Build backend — auto-includes package data, supports `force-include` for frontend assets |
| `sentence-transformers[onnx]` | latest       | Embedding inference via ONNX Runtime without PyTorch                                     |
| `onnxruntime`                 | (transitive) | Pulled in by `sentence-transformers[onnx]`, replaces PyTorch for inference               |

---

# Area 3: Docker Execution, Cleanup & Signal Handling

**Spec**: [specs/001-core-platform/spec.md](specs/001-core-platform/spec.md) | **Date**: 2026-03-04
**Scope**: Docker SDK action execution, label-based cleanup, signal handling, stale recovery, docker_exec checks

---

## Topic 1: Docker SDK Action Execution

### Decision

Implement an **action executor** that takes a list of typed action objects and executes them sequentially against the Docker SDK. Each action type maps to exactly one SDK method. All created resources are labelled `eduops.session=<uuid>`. The executor maintains a **rollback stack** — each successful action pushes a compensating undo action. On failure, the stack is unwound in reverse order.

**Action → SDK mapping**:

| Action Type      | SDK Call                                                         | Label Injection                             |
| ---------------- | ---------------------------------------------------------------- | ------------------------------------------- |
| `pull_image`     | `client.images.pull(image, tag)`                                 | N/A (images are shared, not session-scoped) |
| `build_image`    | `client.images.build(fileobj=..., tag=..., labels=..., rm=True)` | `labels={"eduops.session": session_id}`     |
| `create_network` | `client.networks.create(name, labels=..., driver="bridge")`      | `labels={"eduops.session": session_id}`     |
| `create_volume`  | `client.volumes.create(name, labels=...)`                        | `labels={"eduops.session": session_id}`     |
| `run_container`  | `client.containers.run(detach=True, labels=..., ...)`            | `labels={"eduops.session": session_id}`     |

**Rollback stack** (LIFO):

```python
rollback_stack: list[Callable] = []

for action in scenario.setup_actions:
    try:
        result = execute_action(client, session_id, action)
        rollback_stack.append(make_undo(client, action, result))
    except ActionError as e:
        logger.error(f"Action {action.type} failed: {e}")
        await rollback(rollback_stack)
        raise SetupError(f"Setup failed at {action.type}: {e}") from e
```

Each undo function is a closure:

| Action Type      | Undo                                                                    |
| ---------------- | ----------------------------------------------------------------------- |
| `pull_image`     | No undo (images are shared; removing would break other uses)            |
| `build_image`    | `client.images.remove(image_tag, force=True)`                           |
| `create_network` | `network.remove()`                                                      |
| `create_volume`  | `volume.remove(force=True)`                                             |
| `run_container`  | `container.stop(timeout=5)` then `container.remove(force=True, v=True)` |

**Error handling per action type**:

- **`pull_image`**: Catch `docker.errors.APIError` and `requests.exceptions.ConnectionError`. Use `client.images.pull()` with no built-in timeout — wrap in `concurrent.futures.ThreadPoolExecutor` with a 120-second timeout (`future.result(timeout=120)`). If the image already exists locally (check via `client.images.get()` + `ImageNotFound`), the pull is still attempted (ensures latest tag), but a failure is non-fatal if the local image exists.
- **`build_image`**: Wrap inline Dockerfile content in `io.BytesIO`. Catch `docker.errors.BuildError` — log the build log from `e.build_log` for diagnostics. Always pass `rm=True` to clean intermediate containers.
- **`create_network`**: Catch `docker.errors.APIError`. The `check_duplicate=True` parameter prevents name collisions. Name networks with the session ID prefix (e.g., `eduops-{session_id[:8]}-{name}`) to avoid clashing with user networks.
- **`create_volume`**: Catch `docker.errors.APIError`. Name volumes with the session ID prefix for the same reason.
- **`run_container`**: Catch `docker.errors.APIError` for port conflicts (409 Conflict), `docker.errors.ContainerError` for immediate exit, `docker.errors.ImageNotFound` if the image wasn't pulled correctly. Name containers with the session ID prefix. Pass `detach=True` so the call doesn't block.

### Rationale

**Sequential execution with rollback** is the correct pattern for action sequences where later actions depend on earlier ones (e.g., `run_container` depends on `create_network`). This is the "saga" pattern from distributed systems, applied locally.

**Why not parallel execution**: Actions have implicit dependencies — a container can't start until its network and volume exist. The scenario schema defines action order explicitly (it's a list, not a DAG). Sequential execution respects this ordering and makes error attribution unambiguous.

**Why label everything**: Labels are the only reliable mechanism for claiming ownership of Docker resources across process restarts. Container names can be reused, IDs are opaque. Labels survive daemon restarts and are queryable via `filters={"label": ...}`. The spec mandates `eduops.session=<uuid>` on every created resource.

**Why not label pulled images**: Pulled images are shared infrastructure. Labelling them with a session ID would require custom image tags (wasteful) and removing them on cleanup could break other sessions or user workflows.

**Why closures for undo**: Each undo captures the exact resource reference (the `Network` object, the `Container` object) returned by the creation call. This avoids re-querying by name or ID during rollback, which could fail if the resource is in a partially-created state.

### Alternatives Considered

| Alternative                                             | Why Rejected                                                                                                                                                                                            |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fire-and-forget (no rollback)                           | Leaves orphaned resources on failure. The user would need to manually clean up networks/volumes from a partially-started scenario. Unacceptable UX.                                                     |
| Transaction-style "dry run" validation before execution | Docker has no dry-run API. Pre-validation can check image availability and port conflicts, but can't guarantee success (TOCTOU race). Pre-checks are useful as optimization but don't replace rollback. |
| Store action results in DB for deferred rollback        | Over-engineered for single-user local tool. The rollback stack in memory is sufficient — if the process crashes mid-setup, the stale recovery mechanism (Topic 4) handles it via label queries.         |
| Parallel action execution with a dependency DAG         | Adds significant complexity (topological sort, concurrent error handling, partial rollback of parallel actions). For 3–5 actions taking <5 seconds total, sequential execution is fast enough.          |
| Docker Compose (shell out to `docker compose up`)       | Violates the no-shell-strings constraint. Also loses fine-grained error handling and rollback control.                                                                                                  |

---

## Topic 2: Label-Based Cleanup

### Decision

Implement cleanup as a **fixed-order, best-effort sweep** that queries Docker by label and removes resources in dependency order: **stop containers → remove containers → remove networks → remove volumes**. Each step catches and logs errors but continues to the next resource. The function is idempotent — safe to call multiple times.

**Implementation**:

```python
def cleanup_session(client: docker.DockerClient, session_id: str) -> None:
    label_filter = {"label": f"eduops.session={session_id}"}

    # 1. Stop running containers (graceful, 10s timeout)
    containers = client.containers.list(
        all=True, filters=label_filter
    )
    for c in containers:
        try:
            if c.status == "running":
                c.stop(timeout=10)
        except docker.errors.NotFound:
            pass  # already gone
        except docker.errors.APIError as e:
            logger.warning(f"Failed to stop container {c.short_id}: {e}")

    # 2. Remove containers
    for c in containers:
        try:
            c.remove(force=True, v=True)
        except docker.errors.NotFound:
            pass  # already removed
        except docker.errors.APIError as e:
            logger.warning(f"Failed to remove container {c.short_id}: {e}")

    # 3. Remove networks
    networks = client.networks.list(filters=label_filter)
    for n in networks:
        try:
            n.remove()
        except docker.errors.NotFound:
            pass
        except docker.errors.APIError as e:
            logger.warning(f"Failed to remove network {n.name}: {e}")

    # 4. Remove volumes
    volumes = client.volumes.list(filters=label_filter)
    for v in volumes:
        try:
            v.remove(force=True)
        except docker.errors.NotFound:
            pass
        except docker.errors.APIError as e:
            logger.warning(f"Failed to remove volume {v.name}: {e}")
```

**Edge cases handled**:

| Edge Case                                           | Handling                                                                                                                                                                                                           |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Container already stopped                           | `c.status` check before `stop()`. Even without it, `stop()` on an exited container is a no-op (returns immediately).                                                                                               |
| Container already removed (by another cleanup call) | Catch `docker.errors.NotFound` and continue.                                                                                                                                                                       |
| Network still in use (container still connected)    | The ordering (remove containers first, then networks) prevents this. If it happens anyway (race condition), `APIError` is caught and logged. A retry after a short delay could be added but is unnecessary for v1. |
| Volume still attached to a container                | Same as networks — ordering prevents this. `force=True` on `volume.remove()` removes even if a stopped container still references it.                                                                              |
| Docker daemon unreachable                           | `DockerException` / `ConnectionError` propagates up. Cleanup is best-effort — if Docker is down, there's nothing to clean up.                                                                                      |
| Empty session (no resources to clean)               | Each `list()` call returns an empty list. The function completes instantly.                                                                                                                                        |

**Container list with `all=True`**: Critical — without `all=True`, `containers.list()` only returns running containers. Stopped/exited containers from a crashed scenario would be missed.

### Rationale

**Fixed dependency order** is essential because Docker enforces referential integrity:

- A network cannot be removed while a container is connected to it.
- A volume cannot be removed while mounted by a running container (though `force=True` handles stopped containers).

Removing containers first breaks all dependencies, making subsequent network and volume removal safe.

**Best-effort with logging** is the correct cleanup strategy for a local tool. Hard failures during cleanup should not crash the application or block the user from starting a new session. Logging ensures debuggability.

**Idempotency** is required because cleanup may be triggered by multiple paths: explicit session end, signal handler, stale recovery. Making it safe to call multiple times eliminates coordination complexity.

**Why not `docker prune` APIs**: `client.containers.prune()`, `client.networks.prune()`, `client.volumes.prune()` remove **all** unused resources, not just session-labelled ones. This would destroy the user's non-eduops resources. Label-filtered `list()` + individual `remove()` is the only safe approach. The prune APIs do accept label filters, but their semantics are "remove unused resources matching filter" — a running container's network wouldn't be pruned even with the label. Individual removal with explicit ordering is more predictable.

### Alternatives Considered

| Alternative                                        | Why Rejected                                                                                                                                                                                                          |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docker system prune` with filters                 | Prune APIs have "unused" semantics that don't match "remove everything for this session." A running container's volume wouldn't be pruned. Individual removal is more explicit and reliable.                          |
| Reverse the creation order from the rollback stack | Only works if the original setup completed and the stack is in memory. Doesn't work for stale recovery (Topic 4) or cleanup after a process crash. Label-based discovery is the universal mechanism.                  |
| Remove in parallel (asyncio.gather)                | Adds complexity for negligible speedup. Cleanup of 3–5 resources takes <2 seconds sequentially. Parallel removal can hit race conditions (e.g., removing a network while a container is still being removed).         |
| Single `docker compose down` equivalent            | No Compose files to target. Resources are created individually by the action executor.                                                                                                                                |
| Track resource IDs in the database and iterate     | Adds DB dependency to cleanup. If the DB is corrupted or the process crashed before writing resource IDs, cleanup fails. Label-based discovery works even after a crash because the source of truth is Docker itself. |

---

## Topic 3: Signal Handling for Cleanup

### Decision

Use **FastAPI's lifespan context manager** for the shutdown cleanup path. Do **not** install custom `SIGINT`/`SIGTERM` handlers — let uvicorn handle signals and translate them into ASGI lifespan shutdown. In the lifespan's post-`yield` block, run cleanup for any active session.

**Implementation**:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    recover_stale_sessions(docker_client)  # Topic 4
    yield
    # Shutdown — triggered by SIGINT/SIGTERM via uvicorn
    if active_session := get_active_session():
        logger.info(f"Shutting down: cleaning session {active_session.id}")
        cleanup_session(docker_client, active_session.id)
        mark_session_closed(active_session.id)

app = FastAPI(lifespan=lifespan)
```

### Rationale

**Uvicorn's signal handling**: Uvicorn installs its own `SIGINT` and `SIGTERM` handlers. On receiving either signal:

1. It sets a shutdown flag.
2. It stops accepting new connections.
3. It triggers the ASGI lifespan shutdown event.
4. It waits for in-flight requests to complete (up to `--timeout-graceful-shutdown`).
5. It exits.

The ASGI lifespan shutdown event is delivered to FastAPI, which resumes the lifespan context manager past the `yield`. This is the **designed, documented integration point** for shutdown cleanup.

**Why not custom signal handlers**: Installing `signal.signal(SIGINT, handler)` or `signal.signal(SIGTERM, handler)` from application code **conflicts with uvicorn's own handlers**. The last handler registered wins, so:

- If the app registers first and uvicorn overwrites → the app handler never fires.
- If uvicorn registers first and the app overwrites → uvicorn's graceful shutdown breaks (no connection draining, no lifespan event).
- Using `loop.add_signal_handler()` in asyncio has the same problem — uvicorn uses this internally.

The lifespan approach avoids all conflicts because it works _with_ uvicorn's signal handling rather than competing with it.

**Timeout considerations**: Set `--timeout-graceful-shutdown=30` when launching uvicorn. This gives the lifespan shutdown block 30 seconds to complete Docker cleanup. For a session with 3–5 containers, cleanup typically takes 5–15 seconds (dominated by `container.stop(timeout=10)`). The 30-second budget is sufficient.

If a second `SIGINT` arrives during graceful shutdown, uvicorn force-exits immediately. The stale recovery mechanism (Topic 4) handles any resources left behind.

**`atexit` as a belt-and-suspenders fallback**: Register an `atexit.register(cleanup_all_sessions)` handler as a last resort. `atexit` runs during normal interpreter shutdown but **not** on `SIGKILL` or abnormal termination. It is redundant with the lifespan approach but harmless and provides coverage for edge cases where lifespan shutdown doesn't complete (e.g., bug in the async cleanup code).

```python
import atexit

def _atexit_cleanup():
    """Last-resort cleanup. Runs during normal interpreter shutdown."""
    try:
        client = docker.from_env()
        for session_id in get_all_active_session_ids():
            cleanup_session(client, session_id)
    except Exception:
        pass  # Best effort — logging may not work during atexit

atexit.register(_atexit_cleanup)
```

### Alternatives Considered

| Alternative                                             | Why Rejected                                                                                                                                                                                                         |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Custom `signal.signal(SIGTERM, handler)`                | Conflicts with uvicorn's signal handling. Either the custom handler or uvicorn's handler is overwritten. Cannot coexist reliably.                                                                                    |
| `loop.add_signal_handler(signal.SIGTERM, handler)`      | Same conflict — uvicorn uses this internally. Overwriting it breaks graceful shutdown.                                                                                                                               |
| Wrap uvicorn in a parent process that handles signals   | Over-engineered. Adds process management complexity (fork, waitpid, signal forwarding). The lifespan approach achieves the same result with zero additional infrastructure.                                          |
| Rely solely on stale recovery (Topic 4) at next startup | Leaves resources running between crashes — containers consume CPU/memory, ports are occupied. Cleanup on shutdown is necessary for good resource hygiene. Stale recovery is the fallback, not the primary mechanism. |
| `atexit` as the primary mechanism                       | `atexit` doesn't run on `SIGKILL` or `os._exit()`. It also runs _after_ the event loop is closed, so async cleanup code can't run. It's only useful as a synchronous, best-effort fallback.                          |
| Background watchdog thread that monitors signals        | Adds threading complexity. The watchdog would need to coordinate with the main thread's event loop. The lifespan pattern is simpler and more Pythonic.                                                               |

---

## Topic 4: Stale Session Recovery

### Decision

On application startup (in the lifespan's pre-`yield` block), query Docker for **any** resources with the label key `eduops.session` and run the standard cleanup procedure for each unique session ID found. Also mark those sessions as `abandoned` in the database.

**Implementation**:

```python
def recover_stale_sessions(client: docker.DockerClient) -> None:
    """Detect and clean up orphaned resources from previous crashes."""
    stale_session_ids: set[str] = set()

    # Discover all eduops-labelled resources
    for container in client.containers.list(
        all=True, filters={"label": "eduops.session"}
    ):
        sid = container.labels.get("eduops.session")
        if sid:
            stale_session_ids.add(sid)

    for network in client.networks.list(filters={"label": "eduops.session"}):
        sid = network.attrs.get("Labels", {}).get("eduops.session")
        if sid:
            stale_session_ids.add(sid)

    for volume in client.volumes.list(filters={"label": "eduops.session"}):
        sid = volume.attrs.get("Labels", {}).get("eduops.session")
        if sid:
            stale_session_ids.add(sid)

    if not stale_session_ids:
        logger.info("No stale sessions found.")
        return

    logger.info(f"Found {len(stale_session_ids)} stale session(s): {stale_session_ids}")

    for session_id in stale_session_ids:
        logger.info(f"Cleaning stale session: {session_id}")
        cleanup_session(client, session_id)  # Reuses Topic 2 cleanup
        mark_session_status(session_id, "abandoned")

    logger.info("Stale session recovery complete.")
```

**Key design points**:

1. **Query by label key only**: `filters={"label": "eduops.session"}` matches any resource with that label key, regardless of value. This discovers resources from _all_ previous sessions, not just one.
2. **Union across resource types**: A partially-cleaned previous crash might have left only volumes (if containers and networks were cleaned but volumes weren't). Querying all three resource types and taking the union of session IDs ensures complete discovery.
3. **Reuse `cleanup_session`**: The same cleanup function from Topic 2 handles the actual removal. No separate "stale cleanup" logic needed.
4. **Update DB state**: Sessions that were `active` in the DB but whose resources are now orphaned are marked as `crashed`. This provides auditability and prevents the UI from showing a "resume" option for a dead session.
5. **Runs synchronously before `yield`**: Stale recovery completes before the app starts accepting requests. This ensures no port conflicts or resource name collisions when starting new sessions.

### Rationale

**Docker as the source of truth**: The database may or may not have accurate state after a crash (the process might have crashed before a DB write). Docker labels are the authoritative record of what resources exist. By querying Docker directly, recovery works regardless of DB state.

**Why scan all three resource types**: A crash can happen at any point during cleanup. If the process crashed after removing containers but before removing volumes, only volumes remain. Scanning containers alone would miss them.

**Why block startup**: If stale resources occupy ports or names that a new session needs, the new session's setup would fail with confusing errors. Cleaning first guarantees a fresh start. The spec mandates stale cleanup within 15 seconds — for a handful of resources this is easily met.

**Why not run recovery in the background**: Background recovery introduces a race condition — a new session could start before the old session's ports are freed. Since recovery is fast (dominated by `container.stop()`), blocking startup is acceptable.

### Alternatives Considered

| Alternative                                                                   | Why Rejected                                                                                                                                                                                                                                                |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Track resource IDs in DB, check DB on startup                                 | DB may be stale or corrupted after a crash. Docker is the ground truth for what resources actually exist. DB-based tracking is a useful optimization (avoids scanning) but can't be the sole mechanism.                                                     |
| Periodic background sweep (e.g., every 60s)                                   | Doesn't address the startup problem (port conflicts on new sessions). Adds continuous overhead for a rare event (crashes). On-startup sweep is simpler and sufficient.                                                                                      |
| Use Docker's `--rm` flag on containers                                        | `--rm` removes the container on exit, but only if the Docker daemon is running. If the daemon restarts, `--rm` containers may persist. Also doesn't help with networks/volumes. Useful as a supplementary measure but doesn't replace label-based recovery. |
| Require the user to manually run cleanup (`eduops cleanup`)                   | Poor UX. The user may not know resources are orphaned. Automatic recovery is a basic hygiene expectation.                                                                                                                                                   |
| Use Docker container restart policy `on-failure` and let containers self-heal | Wrong goal — we want to _remove_ orphaned resources, not restart them. A crashed eduops session's containers should be destroyed, not restarted.                                                                                                            |

---

## Topic 5: `docker_exec` as a Success Check

### Decision

Run `container.exec_run(cmd)` where `cmd` is a **list of strings** (no shell interpretation). Wrap the call with a **30-second timeout** using `concurrent.futures.ThreadPoolExecutor`. Capture stdout (and optionally stderr) and match against `expect_stdout` using simple string containment or exact match.

**Implementation**:

```python
import concurrent.futures

def run_exec_check(
    container: docker.models.containers.Container,
    cmd: list[str],
    expect_stdout: str,
    timeout: float = 30.0,
) -> CheckResult:
    """
    Run a command inside a container and check stdout against expected output.

    cmd must be a list of strings — no shell interpretation.
    Example: ["cat", "/etc/nginx/nginx.conf"]
    """
    def _exec():
        return container.exec_run(
            cmd=cmd,
            stdout=True,
            stderr=False,   # capture stdout only for matching
            demux=False,
            tty=False,
        )

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_exec)
            result = future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return CheckResult(
            passed=False,
            message=f"Command timed out after {timeout}s: {cmd}",
        )
    except docker.errors.APIError as e:
        return CheckResult(
            passed=False,
            message=f"Docker API error running exec: {e}",
        )

    exit_code = result.exit_code
    stdout = result.output.decode("utf-8", errors="replace").strip()

    if exit_code != 0:
        return CheckResult(
            passed=False,
            message=f"Command exited with code {exit_code}. stdout: {stdout[:500]}",
        )

    if expect_stdout in stdout:
        return CheckResult(passed=True, message="Check passed.")
    else:
        return CheckResult(
            passed=False,
            message=f"Expected stdout to contain '{expect_stdout}', got: {stdout[:500]}",
        )
```

**Key design points**:

1. **`cmd` is always a list**: `exec_run(cmd=["cat", "/etc/hosts"])` — Docker API sends this as an exec array, no shell interpretation. This is mandated by the no-shell-strings constraint. The scenario schema must validate that `cmd` is `list[str]`, never a bare string.

2. **Timeout via `ThreadPoolExecutor`**: `exec_run()` is a blocking call (the Docker SDK is synchronous). It blocks until the command completes. A hung command (e.g., `cat` on a FIFO with no writer) would block forever. Wrapping in a `ThreadPoolExecutor` with `future.result(timeout=30)` provides the required 30-second timeout. When the timeout fires, `TimeoutError` is raised in the calling thread. The exec'd process continues running inside the container but the check reports failure.

3. **`stderr=False`**: Only stdout is captured for matching against `expect_stdout`. Stderr is ignored during matching to avoid false negatives from warning messages. If diagnostics are needed, a separate call with `stderr=True, demux=True` can capture both streams independently.

4. **`demux=False`**: With `demux=False`, stdout and stderr are interleaved in a single bytes output. Since we set `stderr=False`, only stdout is returned. If we wanted both streams separately, we'd use `demux=True` which returns a `(stdout_bytes, stderr_bytes)` tuple.

5. **Exit code check**: A non-zero exit code is an automatic failure, regardless of stdout content. This catches cases where the command fails but produces partial output that might accidentally match `expect_stdout`.

6. **Output truncation in error messages**: Stdout is truncated to 500 characters in error messages to avoid enormous log entries from commands that dump large outputs.

### Rationale

**`ThreadPoolExecutor` for timeouts**: The Docker SDK's `exec_run` has no timeout parameter. The only way to impose a time limit is from the calling side. Options:

- `threading.Timer` + killing the thread: Python threads can't be killed. The Timer can set a flag, but the blocking `exec_run` won't check it.
- `signal.alarm()`: Only works on the main thread, not from async contexts or worker threads.
- `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=N)`: Cleanly raises `TimeoutError` after N seconds. The background thread continues (the exec API call is still in flight), but the check result is returned immediately. This is the standard Python pattern for timeouts on blocking calls.
- `asyncio.wait_for` + `asyncio.to_thread`: Equivalent to the ThreadPoolExecutor approach, but async. Either works; the sync version is simpler when called from the check runner which iterates checks sequentially, provided that the whole check runner is itself executed off the ASGI event loop (e.g. via `await asyncio.to_thread(run_checks, ...)` from the API layer).

**Why list-of-strings, not a shell string**: `exec_run(cmd="cat /etc/hosts")` would work (Docker SDK accepts a string and splits it), but the no-shell-strings constraint exists to prevent injection and ensure predictable parsing. A list `["cat", "/etc/hosts"]` is unambiguous — no quoting issues, no word splitting, no glob expansion. The scenario schema enforces this at validation time.

**Why `expect_stdout` uses string containment**: Exact match is too brittle — whitespace, trailing newlines, or minor formatting differences cause false failures. Containment (`in` operator) is resilient to surrounding output while still verifying the key content. For v1, this is sufficient. Regex matching could be added as a future check variant if needed.

**What happens to the exec'd process on timeout**: The exec'd process continues running inside the container. The Docker SDK doesn't provide a way to kill a specific exec instance. For a 30-second check, this is acceptable — the process will either complete on its own or be killed when the container is stopped during cleanup. If runaway exec processes become a problem, `container.exec_run` with `detach=True` + polling the exec inspect API would give more control, but this adds significant complexity for v1.

### Alternatives Considered

| Alternative                                                 | Why Rejected                                                                                                                                                                                                                                                                                                                  |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `exec_run(cmd="shell string")` with string splitting        | Violates no-shell-strings constraint. Docker SDK does accept a string and uses `shlex.split()`, but this is implicit and fragile (platform-dependent splitting, no quoting guarantees).                                                                                                                                       |
| `exec_run(cmd=["sh", "-c", "some command"])`                | Wrapping in `sh -c` reintroduces shell interpretation — glob expansion, variable substitution, piping. This defeats the purpose of the typed command constraint. Only acceptable if the scenario explicitly requires shell features (not in v1).                                                                              |
| `subprocess.run(["docker", "exec", container_id, ...])`     | Violates the no-shell-strings/subprocess constraint. Bypasses SDK connection pooling. Loses structured error handling.                                                                                                                                                                                                        |
| `exec_run` with `stream=True` and line-by-line matching     | Adds complexity for no benefit when checking final output. Streaming is useful for long-running commands or real-time output, but success checks are short-lived (30s max). Streaming would also complicate the timeout implementation.                                                                                       |
| Docker SDK `exec_create` + `exec_start` (low-level API)     | The low-level API separates creation from execution and provides more control (e.g., `exec_inspect` for exit code). But `exec_run` wraps both and is simpler. The low-level API would only be needed if we required streaming exec output or fine-grained exec lifecycle control. Not needed for v1.                          |
| `asyncio.wait_for(asyncio.to_thread(exec_run), timeout=30)` | Functionally equivalent to the ThreadPoolExecutor approach but requires an async context. Either works. The sync version is chosen because the check runner iterates checks sequentially in a synchronous loop and is run via `to_thread` from the API layer. If the check runner becomes fully async, this is a viable migration. |
| `signal.alarm` for timeout                                  | Only works on the main thread. The check runner executes inside a thread (called from the async API via `to_thread`). `signal.alarm` would raise `SIGALRM` on the main thread, not the worker thread.                                                                                                                         |

---

## Summary of Decisions

| #   | Topic               | Decision                                                                                                                                                                                                         |
| --- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Action execution    | Sequential execution with typed action→SDK mapping. Rollback stack with compensating undo closures. All created resources labelled `eduops.session=<uuid>`.                                                      |
| 2   | Label-based cleanup | Fixed-order sweep: stop containers → remove containers → remove networks → remove volumes. Best-effort with `NotFound` handling. Idempotent.                                                                     |
| 3   | Signal handling     | Use FastAPI lifespan post-`yield` for shutdown cleanup. Do not install custom signal handlers — let uvicorn handle SIGINT/SIGTERM and deliver the ASGI shutdown event. `atexit` as belt-and-suspenders fallback. |
| 4   | Stale recovery      | On startup (pre-`yield`), query Docker for any `eduops.session`-labelled resources across all resource types. Union session IDs, run standard cleanup for each. Block startup until complete.                    |
| 5   | docker_exec checks  | `container.exec_run(cmd=list[str])` with ThreadPoolExecutor 30s timeout. Check exit code, then match stdout against `expect_stdout` using string containment. No shell, no streaming.                            |

## Dependencies

No new dependencies required — all patterns use the `docker` (Python SDK) package and Python stdlib (`concurrent.futures`, `threading`, `contextlib`, `atexit`).

---

# Area 4: LLM Integration

**Scope**: LLM client, structured output, coaching prompts, review prompts, config format (FR-011, FR-012, FR-015, FR-017, FR-024, FR-025)

---

## Topic 1: OpenAI-Compatible Client

### Decision

Use the `openai` Python package (v1.0+) with custom `base_url`. Do not use `litellm` or raw `httpx`.

### Rationale

The `openai` package natively supports `base_url`, making it a universal client for OpenAI, Gemini (via `/v1beta/openai/`), OpenRouter, and any compatible proxy. It provides structured output via `.parse()`, async support via `AsyncOpenAI`, built-in retries, and `httpx`-based timeout control. Adding `litellm` (~100+ transitive deps) for a single-user tool calling one provider at a time is unnecessary.

### Alternatives Considered

| Alternative     | Why Rejected                                                                                                           |
| --------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `litellm`       | ~100+ transitive deps, provider routing complexity unnecessary for single-user local tool, version-coupling risk       |
| Raw `httpx`     | Requires reimplementing retry logic, SSE parsing, error hierarchy, response parsing — all provided by `openai` package |
| `anthropic` SDK | Only works with Anthropic native API, not OpenAI-compatible format; Anthropic reachable via OpenRouter                 |

---

## Topic 2: Structured JSON Output from LLMs

### Decision

Schema-in-prompt + `json.loads()` + Pydantic `model_validate()` as the primary path, with `response_format` (JSON schema) as an enhancement when the provider supports it. One automatic retry with validation errors fed back to the LLM per spec.

### Rationale

Schema-in-prompt works universally across all OpenAI-compatible providers. Modern LLMs (GPT-4o, Claude 3.5, Gemini 1.5) produce valid JSON from schema-in-prompt >95% of the time. The retry mechanism (already mandated by spec) handles the remaining cases. `response_format` with `json_schema` type gives 100% schema compliance on supporting providers (OpenAI, some OpenRouter models) but isn't universally supported.

Implementation: try `response_format={"type": "json_object"}` if available, embed full schema in system prompt regardless, parse with `json.loads()`, validate with Pydantic, retry once on failure.

### Alternatives Considered

| Alternative                          | Why Rejected                                                          |
| ------------------------------------ | --------------------------------------------------------------------- |
| `response_format` only (no fallback) | Breaks for providers that don't support it                            |
| Function calling / tool use          | Semantically wrong for scenario generation; variable provider support |
| `instructor` library                 | Adds dependency for ~30 lines of retry logic                          |

---

## Topic 3: Socratic Coaching Prompt Design

### Decision

Two separate system prompts — Socratic (default) and direct-answer (triggered by "Show Answer"). Backend switches prompts; user cannot manipulate mode via chat.

### Rationale

LLMs follow unconditional system prompts more reliably than conditional ones. A single prompt with "be Socratic unless mode=direct" creates an exploitable seam — users could social-engineer the model. Two prompts eliminate this. The "Show Answer" action is a backend decision (UI button click), not a user message. Chat history is preserved across mode switches so the direct answer references prior Socratic exchanges.

### Alternatives Considered

| Alternative                                 | Why Rejected                               |
| ------------------------------------------- | ------------------------------------------ |
| Single prompt with mode flag                | Exploitable by users; harder to tune       |
| Reset chat history on mode switch           | Loses context from Socratic exchange       |
| Append special user message for mode switch | Fragile, pollutes history, can be mimicked |

---

## Topic 4: LLM Review Prompt Design

### Decision

Structured review prompt with separated context (scenario + docker inspect + logs) from instructions. Request output in three fixed sections: What Went Well (2-3 items), What Could Improve (1-2 items), Next Steps (1-2 items). Optionally request as JSON via a `Review` Pydantic model for reliable frontend parsing.

### Rationale

Fixed section structure produces consistent output across models. Specificity instructions ("reference actual configuration") counteract generic praise. Bounded scope (2-3 items, 1-2 items) prevents both terse and essay-length reviews. Tying next-steps to scenario context creates learning progression rather than generic Docker advice.

### Alternatives Considered

| Alternative                       | Why Rejected                                              |
| --------------------------------- | --------------------------------------------------------- |
| Unstructured "review this" prompt | Inconsistent output format, unpredictable rendering       |
| Rubric-based numeric scoring      | Feels judgmental; scores inconsistent across models       |
| Multi-turn review conversation    | Over-engineered; coaching chat exists for interactive Q&A |

---

## Topic 5: Config File Format for LLM Settings

### Decision

TOML at `~/.eduops/config.toml` with `[llm]` section containing `provider`, `api_key`, `model`, and optional `base_url`.

```toml
[llm]
provider = "openrouter"  # openai | gemini | openrouter | custom
api_key = "sk-..."
model = "gpt-4o"
base_url = ""            # optional; auto-derived from provider
```

Provider determines default `base_url`: openai → `api.openai.com/v1`, gemini → `generativelanguage.googleapis.com/v1beta/openai`, openrouter → `openrouter.ai/api/v1`, custom → must provide `base_url`. Support `EDUOPS_API_KEY` env var as override. `chmod 600` on config file.

### Rationale

`provider` field simplifies UX (user picks from a list, doesn't need to know URLs). Enables provider-specific headers (OpenRouter needs `HTTP-Referer`). TOML is the Python ecosystem standard, readable via `tomllib` (stdlib in 3.11+), human-editable. Per-call settings (temperature, max_tokens) are hardcoded per use case in the prompt module, not user-configurable.

### Alternatives Considered

| Alternative                   | Why Rejected                                      |
| ----------------------------- | ------------------------------------------------- |
| Environment variables only    | Poor UX for non-developers, no interactive setup  |
| JSON config                   | No comments, not human-friendly for hand-editing  |
| YAML config                   | External dependency, implicit typing pitfalls     |
| Keyring / OS credential store | Adds platform-specific complexity; v2 enhancement |

---

## Summary of All Decisions

| Area                | Topic              | Decision                                                                            |
| ------------------- | ------------------ | ----------------------------------------------------------------------------------- |
| **SSE Streaming**   | SSE pattern        | `sse-starlette` `EventSourceResponse` + async generator                             |
| **SSE Streaming**   | Multiplexing       | `asyncio.Queue` fan-in, one thread per container, Docker events watcher             |
| **SSE Streaming**   | Disconnect cleanup | `finally` on `CancelledError`, `threading.Event`, `join(timeout=2)`                 |
| **SSE Streaming**   | Threading model    | Explicit `threading.Thread` per container, `call_soon_threadsafe` bridge            |
| **Packaging**       | Package structure  | `src` layout, `eduops/static/` via hatchling `force-include`                        |
| **Packaging**       | Build workflow     | Manual `npm run build` → `python -m build`; CI enforces sequence                    |
| **Packaging**       | CLI entry point    | `[project.scripts] eduops = "eduops.cli:main"` + `__main__.py`                      |
| **Packaging**       | Heavy deps         | `sentence-transformers[onnx]` replaces PyTorch with ONNX Runtime                    |
| **Packaging**       | Static serving     | `StaticFiles(packages=[("eduops", "static")], html=True)`                           |
| **Packaging**       | Bundled data       | Scenario JSON in `eduops/scenarios/`, embeddings in `eduops/data/` as base64 JSON   |
| **Docker Exec**     | Action execution   | Sequential with rollback stack, typed action→SDK mapping, labelled resources        |
| **Docker Exec**     | Cleanup            | Fixed-order sweep by label, best-effort with `NotFound` handling, idempotent        |
| **Docker Exec**     | Signal handling    | FastAPI lifespan post-`yield`; no custom signal handlers; `atexit` fallback         |
| **Docker Exec**     | Stale recovery     | Pre-`yield` scan for `eduops.session` labels across all resource types              |
| **Docker Exec**     | docker_exec checks | `exec_run(cmd=list[str])`, ThreadPoolExecutor 30s timeout, stdout containment match |
| **LLM Integration** | Client             | `openai` package with custom `base_url`                                             |
| **LLM Integration** | Structured output  | Schema-in-prompt + Pydantic + 1 retry; `response_format` as enhancement             |
| **LLM Integration** | Coaching prompt    | Two separate system prompts (Socratic / direct-answer)                              |
| **LLM Integration** | Review prompt      | Three-section structured template; optional JSON output                             |
| **LLM Integration** | Config format      | TOML `[llm]` section with provider/api_key/model/base_url                           |

## All New Dependencies

| Package                       | Version   | Purpose                                                                       |
| ----------------------------- | --------- | ----------------------------------------------------------------------------- |
| `sse-starlette`               | `>=2.0`   | SSE with ping, send_timeout, disconnect handling                              |
| `hatchling`                   | `>=1.26`  | Build backend with `force-include` for frontend assets                        |
| `sentence-transformers[onnx]` | latest    | Embedding inference via ONNX Runtime (no PyTorch)                             |
| `openai`                      | `>=1.0`   | OpenAI-compatible LLM client                                                  |
| `fastapi`                     | `>=0.110` | Web framework                                                                 |
| `uvicorn[standard]`           | `>=0.27`  | ASGI server                                                                   |
| `docker`                      | `>=7.0`   | Python Docker SDK                                                             |
| `httpx`                       | `>=0.27`  | HTTP client (used by openai internally, also useful for port_responds checks) |
