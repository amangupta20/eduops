from typing import Annotated, Literal
from pydantic import BaseModel, Field

class PullImage(BaseModel):
    action: Literal["pull_image"]
    image: str

class BuildImage(BaseModel):
    action: Literal["build_image"]
    tag: str
    dockerfile_content: str

class CreateNetwork(BaseModel):
    action: Literal["create_network"]
    name: str
    driver: str = "bridge"

class CreateVolume(BaseModel):
    action: Literal["create_volume"]
    name: str

class RunContainer(BaseModel):
    action: Literal["run_container"]
    image: str
    name: str
    ports: dict[str, str] = {}
    volumes: dict[str, str] = {}
    network: str | None = None
    env: dict[str, str] = {}
    command: list[str] | None = None
    detach: bool = True

SetupAction = Annotated[
    PullImage | BuildImage | CreateNetwork | CreateVolume | RunContainer,
    Field(discriminator="action")
]