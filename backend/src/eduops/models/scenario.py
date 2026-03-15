from pathlib import PurePosixPath
from typing import Annotated, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- SETUP ACTIONS (Task 14) ---

class SetupActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class PullImage(SetupActionBase):
    action: Literal["pull_image"]
    image: str

    @field_validator("image")
    @classmethod
    def validate_approved_image(cls, value: str) -> str:
        approved = [
            "nginx:alpine", "httpd:alpine", "python:3.11-slim",
            "alpine:3", "busybox:latest", "node:20-alpine"
        ]
        if value not in approved:
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