# pylint: disable=too-few-public-methods
import factory

from golem import clientconfigdescriptor
from golem.task import taskserver

from tests.factories import p2p as p2p_factory


class TaskServer(factory.Factory):
    class Meta:
        model = taskserver.TaskServer

    node = p2p_factory.Node()
    config_desc = clientconfigdescriptor.ClientConfigDescriptor()
    use_docker_machine_manager = False
