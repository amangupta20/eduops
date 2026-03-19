import io
import logging
import docker
from docker.errors import APIError, BuildError, ImageNotFound
from docker.models.images import Image
from docker.models.networks import Network
from docker.models.volumes import Volume

# Import the strict models you built in Phase 2
from eduops.models.scenario import PullImage, BuildImage, CreateNetwork, CreateVolume

logger = logging.getLogger(__name__)

# Configurable timeout for blocking Docker operations (5 minutes)
DEFAULT_DOCKER_TIMEOUT = 300

class DockerExecutionError(Exception):
    """Custom exception raised when a Docker SDK operation fails."""
    pass

def handle_pull_image(client: docker.DockerClient, action: PullImage, session_id: str) -> Image:
    """Pulls an image from a registry and retags it for session cleanup tracking."""
    logger.info(f"[{session_id}] Pulling image: {action.image}")
    try:
        image = client.images.pull(action.image)
        
        # Docker SDK doesn't allow labeling pulled images. 
        # Instead, we apply a session-specific tag so the teardown script can find it.
        base_name = action.image.split(":")[0]
        session_tag = f"eduops-{session_id}"
        
        image.tag(repository=base_name, tag=session_tag)
        logger.debug(f"[{session_id}] Retagged pulled image as {base_name}:{session_tag}")
        
        return image
    except (APIError, ImageNotFound) as e:
        logger.error(f"[{session_id}] Failed to pull/tag image {action.image}: {e}")
        raise DockerExecutionError(f"Failed to pull/tag image {action.image}") from e

def handle_build_image(client: docker.DockerClient, action: BuildImage, session_id: str) -> Image:
    """Builds an image from an in-memory Dockerfile string and logs the output."""
    logger.info(f"[{session_id}] Building image: {action.tag}")
    
    # Convert the string content into an in-memory byte stream
    dockerfile_obj = io.BytesIO(action.dockerfile_content.encode("utf-8"))
    
    try:
        image, build_logs = client.images.build(
            fileobj=dockerfile_obj,
            custom_context=False,
            tag=action.tag,
            labels={"eduops.session": session_id},
            rm=True,  # Clean up intermediate containers
            timeout=DEFAULT_DOCKER_TIMEOUT # Circuit breaker for infinite loops
        )
        # Safely iterate through the generator to log the build output
        for chunk in build_logs:
            if "stream" in chunk and chunk["stream"].strip():
                logger.debug(f"[{session_id}] Build: {chunk['stream'].strip()}")
        return image
        
    except BuildError as e:
        logger.error(f"[{session_id}] Build failed for {action.tag}")
        # Print the actual Docker failure reason
        for chunk in e.build_log:
            if "stream" in chunk and chunk["stream"].strip():
                logger.error(f"[{session_id}] Build log: {chunk['stream'].strip()}")
        raise DockerExecutionError(f"Failed to build image {action.tag}") from e
        
    except APIError as e:
        logger.error(f"[{session_id}] API error while building {action.tag}: {e}")
        raise DockerExecutionError(f"Failed to build image {action.tag}") from e

def handle_create_network(client: docker.DockerClient, action: CreateNetwork, session_id: str) -> Network:
    """Creates a Docker network and applies the session label."""
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
    """Creates a Docker volume and applies the session label."""
    logger.info(f"[{session_id}] Creating volume: {action.name}")
    try:
        return client.volumes.create(
            name=action.name,
            labels={"eduops.session": session_id}
        )
    except APIError as e:
        logger.error(f"[{session_id}] Failed to create volume {action.name}: {e}")
        raise DockerExecutionError(f"Failed to create volume {action.name}") from e