from golem.docker.environment import DockerEnvironment


class DummyTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/dummy"
    DOCKER_TAG = "1.4.1"
    ENV_ID = "DUMMYPOW"
    SHORT_DESCRIPTION = "Dummy task (example app calculating proof-of-work " \
                        "hash)"
