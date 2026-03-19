import type {
    LogEvent,
    ContainerStartedEvent,
    ContainerExitedEvent,
    DroppedEvent,
    SessionEndedEvent,
} from "../types";

/**
 * A client wrapper for Server-Sent Events (SSE) that provides typed, chainable
 * event handlers for session log streaming.
 */
export interface SseClient {
    onLog: (handler: (event: LogEvent) => void) => SseClient;
    onContainerStarted: (handler: (event: ContainerStartedEvent) => void) => SseClient;
    onContainerExited: (handler: (event: ContainerExitedEvent) => void) => SseClient;
    onDropped: (handler: (event: DroppedEvent) => void) => SseClient;
    onSessionEnded: (handler: (event: SessionEndedEvent) => void) => SseClient;
    onError: (handler: (event: Event) => void) => SseClient;
    /** Closes the underlying EventSource connection. */
    disconnect: () => void;
}

/**
 * Connects to the backend log stream for a given session.
 * Utilizes the browser's native EventSource API, which automatically
 * handles reconnections if the stream drops unexpectedly.
 *
 * @param sessionId - The UUID of the active session
 * @returns An SseClient instance with chainable event handlers
 */
export function connectLogStream(sessionId: string): SseClient {
    const url = `/api/sessions/${encodeURIComponent(sessionId)}/logs`;
    const eventSource = new EventSource(url);

    // Handlers
    let logHandler: ((event: LogEvent) => void) | undefined;
    let containerStartedHandler: ((event: ContainerStartedEvent) => void) | undefined;
    let containerExitedHandler: ((event: ContainerExitedEvent) => void) | undefined;
    let droppedHandler: ((event: DroppedEvent) => void) | undefined;
    let sessionEndedHandler: ((event: SessionEndedEvent) => void) | undefined;
    let errorHandler: ((event: Event) => void) | undefined;

    // Helper to safely parse JSON and dispatch to handler, routing errors to the error handler.
    const parseAndDispatch = <T>(
        e: Event,
        handler: ((event: T) => void) | undefined,
        eventName: string
    ) => {
        if (!handler) return;
        try {
            const data = JSON.parse((e as MessageEvent).data);
            handler(data);
        } catch (err) {
            // Route parse failures to the registered error handler if available
            if (errorHandler) {
                errorHandler(new ErrorEvent("error", { 
                    message: `Failed to parse '${eventName}' event`,
                    error: err 
                }));
            } else {
                console.error(`Failed to parse '${eventName}' event`, err);
            }
        }
    };

    // Listeners parsing JSON data payload
    eventSource.addEventListener("log", (e) => parseAndDispatch(e, logHandler, "log"));
    eventSource.addEventListener("container_started", (e) => parseAndDispatch(e, containerStartedHandler, "container_started"));
    eventSource.addEventListener("container_exited", (e) => parseAndDispatch(e, containerExitedHandler, "container_exited"));
    eventSource.addEventListener("dropped", (e) => parseAndDispatch(e, droppedHandler, "dropped"));
    
    eventSource.addEventListener("session_ended", (e) => {
        parseAndDispatch(e, sessionEndedHandler, "session_ended");
        // Streams are explicitly closed by backend, so close client to prevent auto-reconnect loops
        eventSource.close();
    });

    eventSource.addEventListener("error", (e) => {
        if (errorHandler) {
            errorHandler(e);
        } else {
            console.error("SSE connection error", e);
        }
    });

    const client: SseClient = {
        onLog: (handler) => {
            logHandler = handler;
            return client;
        },
        onContainerStarted: (handler) => {
            containerStartedHandler = handler;
            return client;
        },
        onContainerExited: (handler) => {
            containerExitedHandler = handler;
            return client;
        },
        onDropped: (handler) => {
            droppedHandler = handler;
            return client;
        },
        onSessionEnded: (handler) => {
            sessionEndedHandler = handler;
            return client;
        },
        onError: (handler) => {
            errorHandler = handler;
            return client;
        },
        disconnect: () => {
            eventSource.close();
        },
    };

    return client;
}
