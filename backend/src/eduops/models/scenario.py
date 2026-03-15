from typing import Literal
from pydantic import BaseModel

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
    command: str | None = None
    detach: bool = True

SetupAction = PullImage | BuildImage | CreateNetwork | CreateVolume | RunContainer