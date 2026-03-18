import type { HealthStatus } from "../types";

const API_BASE_URL = "/api";

interface ErrorResponse {
    detail?: string;
}

export class ApiError extends Error {
    status: number | null;
    detail?: string;

    constructor(message: string, status: number | null = null, detail?: string) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.detail = detail;
    }
}

type RequestOptions = Omit<RequestInit, "body"> & {
    body?: unknown;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { body, headers, ...init } = options;
    const requestHeaders = new Headers(headers);

    if (body !== undefined && !requestHeaders.has("Content-Type")) {
        requestHeaders.set("Content-Type", "application/json");
    }

    let response: Response;

    try {
        response = await fetch(`${API_BASE_URL}${path}`, {
            ...init,
            headers: requestHeaders,
            body: body === undefined ? undefined : JSON.stringify(body),
        });
    } catch {
        throw new ApiError("Network error. Please check your connection and backend server.");
    }

    if (response.status === 204) {
        return undefined as T;
    }

    const contentType = response.headers.get("content-type") ?? "";
    let payload: unknown = null;

    if (contentType.includes("application/json")) {
        try {
            payload = await response.json();
        } catch {
            throw new ApiError("Received invalid JSON response from server.", response.status);
        }
    }

    if (!response.ok) {
        const errorPayload = payload as ErrorResponse | null;
        const detail = errorPayload?.detail;
        const message = detail ?? `Request failed with status ${response.status}`;

        throw new ApiError(message, response.status, detail);
    }

    return payload as T;
}

export async function getHealth(): Promise<HealthStatus> {
    return request<HealthStatus>("/health", { method: "GET" });
}