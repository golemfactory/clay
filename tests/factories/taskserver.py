# pylint: disable=too-few-public-methods
import random
import factory

from golem import clientconfigdescriptor
from golem.task import taskserver
from golem.task.taskbase import ResultType

from tests.factories import p2p as p2p_factory


class TaskServer(factory.Factory):
    class Meta:
        model = taskserver.TaskServer

    node = p2p_factory.Node()
    config_desc = clientconfigdescriptor.ClientConfigDescriptor()
    use_docker_machine_manager = False


class WaitingTaskResultFactory(factory.Factory):
    class Meta:
        model = taskserver.WaitingTaskResult

    task_id = factory.Faker('uuid4')
    subtask_id = factory.Faker('uuid4')
    result = factory.Faker('text')
    result_type = ResultType.DATA
    computing_time = factory.LazyFunction(lambda: random.randint(100, 20000))
    last_sending_trial = 0
    delay_time = 0
    owner_address = factory.Faker('ipv4')
    owner_port = factory.LazyFunction(lambda: random.randint(30000, 60000))
    owner_key_id = factory.Faker('sha1')
    owner = factory.Faker('sha1')
    package_sha1 = factory.Faker('sha1')
