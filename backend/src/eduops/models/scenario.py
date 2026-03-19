from pathlib import PurePosixPath
from typing import Annotated, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

# The single source of truth for approved external Docker images
APPROVED_IMAGE_LIST = [
    "nginx:alpine", "httpd:alpine", "python:3.11-slim",
    "alpine:3", "busybox:latest", "node:20-alpine"
]

# --- SETUP ACTIONS (Task 14) ---

class SetupActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class PullImage(SetupActionBase):
    action: Literal["pull_image"]
    image: str

    @field_validator("image")
    @classmethod
    def validate_approved_image(cls, value: str) -> str:
        # Use the shared constant!
        if value not in APPROVED_IMAGE_LIST:
            raise ValueError(f"Image '{value}' is not in the approved list. Use build_image for custom setups.")
        return value

class BuildImage(SetupActionBase):
    action: Literal["build_image"]
    tag: str
    dockerfile_content: str

class CreateNetwork(SetupActionBase):
    action: Literal["create_network"]
    name: str
    driver: str = "bridge"

class CreateVolume(SetupActionBase):
    action: Literal["create_volume"]
    name: str

class RunContainer(SetupActionBase):
    action: Literal["run_container"]
    image: str
    name: str
    ports: dict[str, str] = Field(default_factory=dict)
    volumes: dict[str, str] = Field(default_factory=dict)
    network: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    command: list[str] | None = None
    detach: bool = True

SetupAction = Annotated[
    PullImage | BuildImage | CreateNetwork | CreateVolume | RunContainer,
    Field(discriminator="action")
]

# --- SUCCESS CHECKS (Task 15) ---

class SuccessCheckBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class ContainerRunning(SuccessCheckBase):
    type: Literal["container_running"]
    name: str

class PortResponds(SuccessCheckBase):
    type: Literal["port_responds"]
    port: int
    path: str = "/"
    expect_status: int = 200
    expect_body: str | None = None

class DockerExec(SuccessCheckBase):
    type: Literal["docker_exec"]
    container: str
    command: list[str]
    expect_stdout: str

class FileInWorkspace(SuccessCheckBase):
    type: Literal["file_in_workspace"]
    path: str
    expect_content: str | None = None

    @field_validator("path")
    @classmethod
    def validate_workspace_relative_path(cls, value: str) -> str:
        p = PurePosixPath(value)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("path must be workspace-relative and must not contain '..'")
        return value

SuccessCheck = Annotated[
    ContainerRunning | PortResponds | DockerExec | FileInWorkspace,
    Field(discriminator="type")
]

# --- SCENARIO SCHEMA & WORKSPACE (Task 16) ---

class WorkspaceFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str
    content: str

    @field_validator("path")
    @classmethod
    def validate_workspace_relative_path(cls, value: str) -> str:
        # Note: PurePosixPath should already be imported at the top of the file from T015!
        p = PurePosixPath(value)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("path must be workspace-relative and must not contain '..'")
        return value
    
class ScenarioSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str
    description: str
    setup_actions: list[SetupAction]
    # default_factory prevents mutable shared state across instances
    expected_containers: list[str] = Field(default_factory=list) 
    success_checks: list[SuccessCheck]
    hints: list[str] = Field(default_factory=list)
    review_context: str | None = None
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)

def validate_approved_images(schema: ScenarioSchema, approved_list: list[str] | None = None) -> bool:
    """
    Validates that all image references in the scenario's setup actions
    are present in the provided approved_list (defaults to APPROVED_IMAGE_LIST), 
    or were built locally.
    Raises ValueError if an unapproved image is found.
    """
    # Default to our shared constant if no list is provided
    if approved_list is None:
        approved_list = APPROVED_IMAGE_LIST
        
    approved_images = set(approved_list)
    
    # 1. Gather all tags that are built locally within this exact scenario
    built_tags = {
        action.tag for action in schema.setup_actions 
        if getattr(action, "action", None) == "build_image"
    }

    # 2. Validate any action that tries to use an image
    for action in schema.setup_actions:
        if hasattr(action, "image"):
            # Allow it if it's approved OR if we just built it locally
            if action.image not in approved_images and action.image not in built_tags:
                raise ValueError(f"Image '{action.image}' is not in the approved list and was not built locally.")
                
    return True

# --- API MODELS (Task 25) ---

class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    title: str
    description: str
    difficulty: Literal["easy", "medium", "hard"]
    tags: list[str]
    source: Literal["bundled", "generated"]
    created_at: str

class ScenarioDetail(ScenarioSummary):
    hints_count: int
    success_checks_count: int
