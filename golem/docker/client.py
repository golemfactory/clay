from docker import DockerClient as Client
from docker.utils import kwargs_from_env


def local_client():
    """Returns an instance of docker.DockerClient for communicating with
    local docker daemon.
    :returns docker.DockerClient:
    """
    kwargs = kwargs_from_env(assert_hostname=False)
    kwargs["timeout"] = 600
    return Client(**kwargs).api
