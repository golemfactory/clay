
import factory

from golem.task import taskbase


class TaskHeader(factory.Factory):
    class Meta:
        model = taskbase.TaskHeader

    task_id = factory.Faker('uuid4')
    task_owner = factory.SubFactory('tests.factories.p2p.Node')
    environment = "DEFAULT"
