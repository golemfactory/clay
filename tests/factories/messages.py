# pylint: disable=too-few-public-methods
import calendar
import time

import factory

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
    deadline = factory.LazyFunction(lambda: calendar.timegm(time.gmtime()))
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
    task_to_compute = factory.SubFactory(TaskToCompute)


class TaskFailure(factory.Factory):
    class Meta:
        model = tasks.TaskFailure

    subtask_id = factory.Faker('uuid4')
    err = factory.Faker('sentence')
    task_to_compute = factory.SubFactory(TaskToCompute)


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
    task_to_compute = factory.SubFactory(
        TaskToCompute,
        compute_task_def__subtask_id=factory.SelfAttribute('...subtask_id'),
    )
    size = factory.Faker('random_int', min=1 << 20, max=10 << 20)
    multihash = factory.Faker('text')
    secret = factory.Faker('text')


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
    task_to_compute = factory.SubFactory(TaskToCompute)


class ForceReportComputedTask(factory.Factory):
    class Meta:
        model = concents.ForceReportComputedTask

    result_hash = factory.Faker('text')
    report_computed_task = factory.SubFactory(ReportComputedTask)


class AckReportComputedTask(factory.Factory):
    class Meta:
        model = concents.AckReportComputedTask

    subtask_id = factory.Faker('uuid4')
    task_to_compute = factory.SubFactory(
        TaskToCompute,
        compute_task_def__subtask_id=factory.SelfAttribute('...subtask_id'),
    )


class VerdictReportComputedTask(factory.Factory):
    class Meta:
        model = concents.VerdictReportComputedTask

    force_report_computed_task = factory.SubFactory(ForceReportComputedTask)
    ack_report_computed_task = factory.SubFactory(
        AckReportComputedTask,
        subtask_id=factory.SelfAttribute(
            '..force_report_computed_task.report_computed_task.subtask_id',
        ),
        task_to_compute=factory.SelfAttribute(
            '..force_report_computed_task.report_computed_task.task_to_compute',
        ),
    )
