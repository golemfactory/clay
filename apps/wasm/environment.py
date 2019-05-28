from golem.docker.environment import DockerEnvironment


class WasmTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/wasm"
    DOCKER_TAG = "wasm_igor_pr"
    ENV_ID = "WASM"
    SHORT_DESCRIPTION = "WASM Sandbox"
