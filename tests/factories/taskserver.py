# pylint: disable=too-few-public-methods
import random
import factory

from golem import clientconfigdescriptor
from golem.task import taskserver
from golem.task.taskbase import ResultType


class TaskServer(factory.Factory):
    class Meta:
        model = taskserver.TaskServer

    network = factory.SubFactory('tests.factories.network.NativeNetwork')
    node = factory.SubFactory('tests.factories.p2p.Node')
    config_desc = clientconfigdescriptor.ClientConfigDescriptor()
    use_docker_manager = False


class WaitingTaskResultFactory(factory.Factory):
    class Meta:
        model = taskserver.WaitingTaskResult

    task_id = factory.Faker('uuid4')
    subtask_id = factory.Faker('uuid4')
    result = factory.Faker('text')
    result_type = ResultType.DATA
    last_sending_trial = 0
    delay_time = 0
    owner = factory.SubFactory('tests.factories.p2p.Node')
    package_sha1 = factory.Faker('sha1')
    result_size = factory.Faker('random_int', min=1 << 20, max=10 << 20)
