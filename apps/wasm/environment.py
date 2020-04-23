from golem.docker.environment import DockerEnvironment


class WasmTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/wasm"
    DOCKER_TAG = "0.6.0"
    ENV_ID = "WASM"
    SHORT_DESCRIPTION = "WASM Sandbox"

    @classmethod
    def is_single_core(cls):
        return True
