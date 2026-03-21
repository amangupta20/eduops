import io
import logging
from pathlib import Path
import docker
from docker.errors import APIError, BuildError, ImageNotFound, ContainerError
from docker.models.containers import Container
from docker.models.images import Image
from docker.models.networks import Network
from docker.models.volumes import Volume

from eduops.models.scenario import PullImage, BuildImage, CreateNetwork, CreateVolume, RunContainer, SetupAction

logger = logging.getLogger(__name__)

DEFAULT_DOCKER_TIMEOUT = 300

class DockerExecutionError(Exception):
    """Custom exception raised when a Docker SDK operation fails."""
    pass

def handle_pull_image(client: docker.DockerClient, action: PullImage, session_id: str) -> tuple[Image, bool]:
    """Pulls an image from a registry. Returns a tuple of (Image, was_new_pull)."""
    logger.info(f"[{session_id}] Pulling image: {action.image}")
    try:
        was_new = False
        try:
            # Check if we already have it locally
            image = client.images.get(action.image)
            logger.debug(f"[{session_id}] Image {action.image} already exists locally.")
        except ImageNotFound:
            # We don't have it, so we must pull it
            was_new = True
            image = client.images.pull(action.image)
        
        # Apply the session-specific alias tag
        base_name = action.image.split(":")[0]
        session_tag = f"eduops-{session_id}"
        image.tag(repository=base_name, tag=session_tag)
        logger.debug(f"[{session_id}] Retagged image as {base_name}:{session_tag}")
        
        return image, was_new
    except (APIError, ImageNotFound) as e:
        logger.error(f"[{session_id}] Failed to pull/tag image {action.image}: {e}")
        raise DockerExecutionError(f"Failed to pull/tag image {action.image}") from e

def handle_build_image(client: docker.DockerClient, action: BuildImage, session_id: str) -> Image:
    logger.info(f"[{session_id}] Building image: {action.tag}")
    dockerfile_obj = io.BytesIO(action.dockerfile_content.encode("utf-8"))
    try:
        image, build_logs = client.images.build(
            fileobj=dockerfile_obj,
            custom_context=False,
            tag=action.tag,
            labels={"eduops.session": session_id},
            rm=True,
            timeout=DEFAULT_DOCKER_TIMEOUT
        )
        for chunk in build_logs:
            if "stream" in chunk and chunk["stream"].strip():
                logger.debug(f"[{session_id}] Build: {chunk['stream'].strip()}")
        return image
    except BuildError as e:
        logger.error(f"[{session_id}] Build failed for {action.tag}")
        for chunk in e.build_log:
            if "stream" in chunk and chunk["stream"].strip():
                logger.error(f"[{session_id}] Build log: {chunk['stream'].strip()}")
        raise DockerExecutionError(f"Failed to build image {action.tag}") from e
    except APIError as e:
        logger.error(f"[{session_id}] API error while building {action.tag}: {e}")
        raise DockerExecutionError(f"Failed to build image {action.tag}") from e

def handle_create_network(client: docker.DockerClient, action: CreateNetwork, session_id: str) -> Network:
    logger.info(f"[{session_id}] Creating network: {action.name}")
    try:
        return client.networks.create(
            name=action.name,
            driver=action.driver,
            labels={"eduops.session": session_id}
        )
    except APIError as e:
        logger.error(f"[{session_id}] Failed to create network {action.name}: {e}")
        raise DockerExecutionError(f"Failed to create network {action.name}") from e

def handle_create_volume(client: docker.DockerClient, action: CreateVolume, session_id: str) -> Volume:
    logger.info(f"[{session_id}] Creating volume: {action.name}")
    try:
        return client.volumes.create(
            name=action.name,
            labels={"eduops.session": session_id}
        )
    except APIError as e:
        logger.error(f"[{session_id}] Failed to create volume {action.name}: {e}")
        raise DockerExecutionError(f"Failed to create volume {action.name}") from e

def handle_run_container(client: docker.DockerClient, action: RunContainer, session_id: str) -> Container:
    logger.info(f"[{session_id}] Running container from image: {action.image}")
    
    if not action.name:
        raise ValueError(f"[{session_id}] Container name is required but was empty or missing.")

    kwargs = {
        "image": action.image,
        "name": action.name,
        "detach": True, 
        "labels": {"eduops.session": session_id},
    }
    
    # Strictly formatted multi-line IF blocks for Ruff compliance (E701 fix)
    if action.ports:
        kwargs["ports"] = action.ports
    if action.volumes:
        kwargs["volumes"] = action.volumes
    if action.network:
        kwargs["network"] = action.network
    if action.env:
        kwargs["environment"] = action.env
    if action.command:
        kwargs["command"] = action.command

    try:
        container = client.containers.run(**kwargs)
        logger.debug(f"[{session_id}] Successfully started container {action.name} (ID: {container.short_id})")
        return container
    except (ContainerError, ImageNotFound, APIError) as e:
        logger.error(f"[{session_id}] Failed to run container {action.name}: {e}")
        raise DockerExecutionError(f"Failed to run container {action.name}") from e

def execute_setup_actions(client: docker.DockerClient, actions: list[SetupAction], session_id: str) -> None:
    logger.info(f"[{session_id}] Executing {len(actions)} setup actions...")
    created_resources = []
    
    # Fixed trailing slash requirement
    workspace_dir = str(Path.home() / ".eduops" / "workspaces" / session_id) + "/"

    def _resolve_workspace_strings(data):
        if isinstance(data, str):
            return data.replace("{{workspace}}", workspace_dir)
        if isinstance(data, list):
            return [_resolve_workspace_strings(item) for item in data]
        if isinstance(data, dict):
            # Strict dict key/value resolution
            return {
                _resolve_workspace_strings(k) if isinstance(k, str) else k:
                _resolve_workspace_strings(v)
                for k, v in data.items()
            }
        return data

    try:
        for action in actions:
            action_dict = action.model_dump()
            resolved_dict = _resolve_workspace_strings(action_dict)
            resolved_action = action.__class__.model_validate(resolved_dict)
            action_type = resolved_action.action
            
            if action_type == "pull_image":
                img, was_new = handle_pull_image(client, resolved_action, session_id)
                session_tag = f"{resolved_action.image.split(':')[0]}:eduops-{session_id}"
                created_resources.append(("image", session_tag))
                if was_new:
                    # If we downloaded it fresh, mark the original for deletion too!
                    created_resources.append(("image", resolved_action.image))
                
            elif action_type == "build_image":
                img = handle_build_image(client, resolved_action, session_id)
                created_resources.append(("image", img.id))
                
            elif action_type == "create_network":
                net = handle_create_network(client, resolved_action, session_id)
                created_resources.append(("network", net.id))
                
            elif action_type == "create_volume":
                vol = handle_create_volume(client, resolved_action, session_id)
                created_resources.append(("volume", vol.id))
                
            elif action_type == "run_container":
                cont = handle_run_container(client, resolved_action, session_id)
                created_resources.append(("container", cont.id))
                
            else:
                raise DockerExecutionError(f"Unknown setup action type: {action_type}")
                
        logger.info(f"[{session_id}] Successfully executed all {len(actions)} setup actions.")
        
    except Exception as e:
        logger.error(f"[{session_id}] Setup failed: {e}. Initiating rollback...")
        _rollback_resources(client, created_resources, session_id)
        raise DockerExecutionError(f"Setup failed, resources rolled back: {e}") from e

def _rollback_resources(client: docker.DockerClient, resources: list[tuple[str, str]], session_id: str) -> None:
    """Reverses the creation of Docker resources (LIFO), then performs an aggressive label sweep."""
    
    # 1. Standard LIFO Rollback
    for res_type, res_id in reversed(resources):
        logger.info(f"[{session_id}] Rolling back {res_type} {res_id}...")
        try:
            if res_type == "container":
                client.containers.get(res_id).remove(force=True, v=True)
            elif res_type == "network":
                client.networks.get(res_id).remove()
            elif res_type == "volume":
                client.volumes.get(res_id).remove()
            elif res_type == "image":
                client.images.remove(image=res_id, force=True)
        except Exception as cleanup_err:
            logger.error(f"[{session_id}] Failed to rollback {res_type} {res_id}: {cleanup_err}")

    # 2. Aggressive Label Sweep (CodeRabbit constraint)
    logger.info(f"[{session_id}] Performing aggressive label sweep for stranded resources...")
    filters = {"label": f"eduops.session={session_id}"}
    try:
        for c in client.containers.list(all=True, filters=filters):
            c.remove(force=True, v=True)
        for n in client.networks.list(filters=filters):
            n.remove()
        for v in client.volumes.list(filters=filters):
            v.remove()
        for i in client.images.list(filters=filters):
            client.images.remove(image=i.id, force=True)
    except Exception as sweep_err:
        logger.error(f"[{session_id}] Label sweep rollback error: {sweep_err}")