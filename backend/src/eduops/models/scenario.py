from typing import Annotated, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

# The strict base class that rejects hallucinated fields
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
    # Fixed mutable defaults
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