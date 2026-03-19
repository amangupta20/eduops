import type {
    LogEvent,
    ContainerStartedEvent,
    ContainerExitedEvent,
    DroppedEvent,
    SessionEndedEvent,
} from "../types";

export interface SseClient {
    onLog: (handler: (event: LogEvent) => void) => SseClient;
    onContainerStarted: (handler: (event: ContainerStartedEvent) => void) => SseClient;
    onContainerExited: (handler: (event: ContainerExitedEvent) => void) => SseClient;
    onDropped: (handler: (event: DroppedEvent) => void) => SseClient;
    onSessionEnded: (handler: (event: SessionEndedEvent) => void) => SseClient;
    onError: (handler: (event: Event) => void) => SseClient;
    disconnect: () => void;
}

export function connectLogStream(sessionId: string): SseClient {
    const url = `/api/sessions/${sessionId}/logs`;
    const eventSource = new EventSource(url);

    // Handlers
    let logHandler: ((event: LogEvent) => void) | undefined;
    let containerStartedHandler: ((event: ContainerStartedEvent) => void) | undefined;
    let containerExitedHandler: ((event: ContainerExitedEvent) => void) | undefined;
    let droppedHandler: ((event: DroppedEvent) => void) | undefined;
    let sessionEndedHandler: ((event: SessionEndedEvent) => void) | undefined;
    let errorHandler: ((event: Event) => void) | undefined;

    // Listeners parsing JSON data payload
    eventSource.addEventListener("log", (e) => {
        if (logHandler) {
            try {
                logHandler(JSON.parse((e as MessageEvent).data));
            } catch (err) {
                console.error("Failed to parse 'log' event", err);
            }
        }
    });

    eventSource.addEventListener("container_started", (e) => {
        if (containerStartedHandler) {
            try {
                containerStartedHandler(JSON.parse((e as MessageEvent).data));
            } catch (err) {
                console.error("Failed to parse 'container_started' event", err);
            }
        }
    });

    eventSource.addEventListener("container_exited", (e) => {
        if (containerExitedHandler) {
            try {
                containerExitedHandler(JSON.parse((e as MessageEvent).data));
            } catch (err) {
                console.error("Failed to parse 'container_exited' event", err);
            }
        }
    });

    eventSource.addEventListener("dropped", (e) => {
        if (droppedHandler) {
            try {
                droppedHandler(JSON.parse((e as MessageEvent).data));
            } catch (err) {
                console.error("Failed to parse 'dropped' event", err);
            }
        }
    });

    eventSource.addEventListener("session_ended", (e) => {
        if (sessionEndedHandler) {
            try {
                sessionEndedHandler(JSON.parse((e as MessageEvent).data));
            } catch (err) {
                console.error("Failed to parse 'session_ended' event", err);
            }
        }
    });

    eventSource.addEventListener("error", (e) => {
        if (errorHandler) {
            errorHandler(e);
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
