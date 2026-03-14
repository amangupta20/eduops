export type Difficulty = "easy" | "medium" | "hard";
export type Source = "bundled" | "generated";

export interface Scenario {
    id: string;
    title: string;
    description: string;
    difficulty: Difficulty;
    tags: string[];
    source: Source;
    created_at: string;
}

export interface ScenarioDetail extends Scenario {
    hints_count: number;
    success_checks_count: number;
}

export interface ScenarioSearchResult extends Scenario {
    score: number;
}

export type SessionStatus = "active" | "completed" | "abandoned";

export interface Session {
    id: string;
    scenario_id: string;
    status: SessionStatus;
    workspace_path: string;
    started_at: string;
    scenario: {
        title: string;
        description: string;
        difficulty: Difficulty;
        tags: string[];
    };
}

export type CheckType =
    | "container_running"
    | "port_responds"
    | "docker_exec"
    | "file_in_workspace";

export interface CheckResult {
    check_type: CheckType;
    check_name: string;
    passed: boolean;
    message: string;
}

export interface Review {
    what_went_well: string[];
    what_could_improve: string[];
    next_steps: string[];
}

export interface SubmitResponse {
    checks: CheckResult[];
    all_passed: boolean;
    review: Review | null;
    session_status: SessionStatus;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
    role: ChatRole;
    content: string;
    created_at: string;
}

export interface LogEvent {
    container: string;
    line: string;
    timestamp: string;
}

export interface ContainerStartedEvent {
    container: string;
    container_id: string;
}

export interface ContainerExitedEvent {
    container: string;
    container_id: string;
}

export interface DroppedEvent {
    count: number;
    message: string;
}

export type SessionEndedEvent = Record<string, never>;

export interface HealthStatus {
    status: string;
    docker: boolean;
    llm_configured: boolean;
    active_session: string | null;
    scenario_count: number;
}
