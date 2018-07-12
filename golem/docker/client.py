from docker import DockerClient


def local_client():
    """Returns an instance of docker.Client for communicating with
    local docker daemon.
    :returns docker.DockerClient:
    """
    return DockerClient(timeout=600)
