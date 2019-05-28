from golem.docker.environment import DockerEnvironment


class DummyTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/dummy"
    DOCKER_TAG = "dummy_igor_pr"
    ENV_ID = "DUMMYPOW"
    SHORT_DESCRIPTION = "Dummy task (example app calculating proof-of-work " \
                        "hash)"
