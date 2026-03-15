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

class ContainerRunning(BaseModel):
    type: Literal["container_running"]
    name: str

class PortResponds(BaseModel):
    type: Literal["port_responds"]
    port: int
    path: str = "/"
    expect_status: int = 200
    expect_body: str | None = None

class DockerExec(BaseModel):
    type: Literal["docker_exec"]
    container: str
    command: list[str]
    expect_stdout: str

class FileInWorkspace(BaseModel):
    type: Literal["file_in_workspace"]
    path: str
    expect_content: str | None = None

SuccessCheck = ContainerRunning | PortResponds | DockerExec | FileInWorkspace