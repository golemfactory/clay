# pylint: disable=too-few-public-methods
import factory
import time

import factory.fuzzy

from golem_messages.message import base
from golem_messages.message import concents
from golem_messages.message import tasks


class Hello(factory.Factory):
    class Meta:
        model = base.Hello

    rand_val = factory.Faker("pyint")
    proto_id = factory.Faker("pyint")
    node_name = factory.Faker("name")


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


class CannotComputeTask(factory.Factory):
    class Meta:
        model = tasks.CannotComputeTask

    subtask_id = factory.Faker('uuid4')
    task_to_compute = factory.SubFactory(ComputeTaskDef)


class TaskFailure(factory.Factory):
    class Meta:
        model = tasks.TaskFailure

    subtask_id = factory.Faker('uuid4')
    err = factory.Faker('sentence')
    task_to_compute = factory.SubFactory(ComputeTaskDef)


class ReportComputedTask(factory.Factory):
    class Meta:
        model = tasks.ReportComputedTask

    subtask_id = factory.Faker('uuid4')
    result_type = 0
    computation_time = factory.Faker('pyfloat')
    node_name = factory.Faker('name')
    address = factory.Faker('ipv4')
    port = factory.Faker('pyint')
    key_id = factory.Faker('binary', length=64)
    task_to_compute = factory.SubFactory(TaskToCompute)
    size = factory.Faker('pyint')
    checksum = factory.Faker('text')


class SubtaskResultsRejected(factory.Factory):
    class Meta:
        model = tasks.SubtaskResultsRejected

    report_computed_task = factory.SubFactory(ReportComputedTask)

class SubtaskResultsAcceptedFactory(factory.Factory):
    class Meta:
        model = tasks.SubtaskResultsAccepted

    task_to_compute = factory.SubFactory(TaskToCompute)
    payment_ts = factory.LazyFunction(lambda: int(time.time()))

class ServiceRefused(factory.Factory):
    class Meta:
        model = concents.ServiceRefused

    reason = factory.fuzzy.FuzzyChoice(concents.ServiceRefused.REASON)
    subtask_id = factory.Faker('uuid4')
    task_to_compute = factory.SubFactory(ComputeTaskDef)


class ForceReportComputedTask(factory.Factory):
    class Meta:
        model = concents.ForceReportComputedTask

    result_hash = factory.Faker('text')
    task_to_compute = factory.SubFactory(ComputeTaskDef)
