from golem.docker.environment import DockerEnvironment


class WasmTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/wasm"
    DOCKER_TAG = "0.0.1"
    ENV_ID = "WASM"
    SHORT_DESCRIPTION = "WASM Sandbox"
