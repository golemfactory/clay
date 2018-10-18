def _docker_conflict(e: Exception):
    # temporary work-around for an issue affecting anyone updating from
    # earlier golem versions

    raise RuntimeError(
        "Suspected conflict in python `docker` library.\n"
        "Please run `pip uninstall -y docker docker-py` "
        "and re-install golem's requirements. "
    ) from e


try:
    from docker import DockerClient as Client
except ImportError as import_error:
    _docker_conflict(import_error)
from docker.utils import kwargs_from_env  # noqa pylint:disable=wrong-import-position


def local_client():
    """Returns an instance of docker.DockerClient for communicating with
    local docker daemon.
    :returns docker.DockerClient:
    """
    kwargs = kwargs_from_env(assert_hostname=False)
    kwargs["timeout"] = 600

    try:
        return Client(**kwargs).api
    except TypeError as type_error:
        _docker_conflict(type_error)
