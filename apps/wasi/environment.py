from golem.docker.environment import DockerEnvironment


class WasiTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/wasi"
    DOCKER_TAG = "latest"
    ENV_ID = "WASI"
    SHORT_DESCRIPTION = "WASI Sandbox"
