from docker import Client
from docker.utils import kwargs_from_env
import os


def local_client( ):
    """Returns an instance of docker.Client for communicating with
    local docker daemon.
    :returns docker.Client:
    """
    client = Client(**kwargs_from_env(assert_hostname = False))
    return client


def disable_docker():
    """Checks if Docker should be disabled in the current running environment.
    """
    return os.getenv("CIRCLECI")  # Docker not available in CircleCI
