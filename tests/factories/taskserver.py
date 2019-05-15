
import factory
from golem_messages import idgenerator

from golem import clientconfigdescriptor
from golem.task import taskserver


class TaskServer(factory.Factory):
    class Meta:
        model = taskserver.TaskServer

    node = factory.SubFactory(
        'golem_messages.factories.datastructures.p2p.Node',
    )
    config_desc = clientconfigdescriptor.ClientConfigDescriptor()
    use_docker_manager = False


class WaitingTaskResultFactory(factory.Factory):
    class Meta:
        model = taskserver.WaitingTaskResult

    task_id = factory.Faker('uuid4')
    subtask_id = factory.Faker('uuid4')
    result = factory.Faker('text')
    last_sending_trial = 0
    delay_time = 0
    owner = factory.SubFactory(
        'golem_messages.factories.datastructures.p2p.Node',
    )
    package_sha1 = factory.Faker('sha1')
    result_size = factory.Faker('random_int', min=1 << 20, max=10 << 20)

    @factory.post_generation
    def xtask_id(  # pylint: disable=no-self-argument
            wtr: taskserver.WaitingTaskResult,
            _create,
            extracted,
            **_kwargs,
    ):
        value = extracted or idgenerator.generate_id_from_hex(wtr.owner.key)  # noqa pylint: disable=no-member
        wtr.task_id = value

    @factory.post_generation
    def xsubtask_id(  # pylint: disable=no-self-argument
            wtr: taskserver.WaitingTaskResult,
            _create,
            extracted,
            **_kwargs,
    ):
        value = extracted or idgenerator.generate_id_from_hex(wtr.owner.key)  # noqa pylint: disable=no-member
        wtr.subtask_id = value


class WaitingTaskFailureFactory(factory.Factory):
    class Meta:
        model = taskserver.WaitingTaskFailure

    task_id = factory.Faker('uuid4')
    subtask_id = factory.Faker('uuid4')
    err_msg = factory.Faker('text')
    owner = factory.SubFactory(
        'golem_messages.factories.datastructures.p2p.Node',
    )
