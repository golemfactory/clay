from docker import Client
from docker.utils import kwargs_from_env

VERSION = '1.19'  # 'auto' will increase the number of API requests


def local_client():
    """Returns an instance of docker.Client for communicating with
    local docker daemon.
    :returns docker.Client:
    """
    client = Client(version=VERSION, **kwargs_from_env(assert_hostname=False))
    return client
