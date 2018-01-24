import factory
from golem_messages.message import tasks

class TaskOwner(factory.DictFactory):
    node_name = factory.Faker('name')
    key = factory.Faker('binary', length=64)

class ComputeTaskDef(factory.DictFactory):
    class Meta:
        model = tasks.ComputeTaskDef

    task_id = factory.Faker('uuid4')
    subtask_id = factory.Faker('uuid4')
    task_owner = factory.SubFactory(TaskOwner)
    deadline = factory.Faker('pyint')
    src_code = factory.Faker('text')

class TaskToCompute(factory.Factory):
    class Meta:
        model = tasks.TaskToCompute

    requestor_id = factory.Faker('binary', length=64)
    provider_id = factory.Faker('binary', length=64)
    compute_task_def = factory.SubFactory(ComputeTaskDef)

    @classmethod
    def _create(cls, *args, **kwargs):
        instance = super()._create(*args, **kwargs)
        instance.compute_task_def['task_owner']['key'] = instance.requestor_id
        return instance
