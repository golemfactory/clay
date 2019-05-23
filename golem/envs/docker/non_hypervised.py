from golem.docker.hypervisor.dummy import DummyHypervisor
from golem.envs.docker.cpu import DockerCPUEnvironment


class NonHypervisedDockerCPUEnvironment(DockerCPUEnvironment):
    """ This is a temporary class that never uses a hypervisor. It just assumes
        that Docker VM is properly configured if needed. The purpose of this
        class is to use Docker CPU Environment alongside with DockerManager. """

    # TODO: Remove when DockerManager is removed

    @classmethod
    def _get_hypervisor_class(cls):
        return DummyHypervisor
