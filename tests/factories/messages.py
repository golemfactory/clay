# pylint: disable=too-few-public-methods
import calendar
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


class ComputeTaskDef(factory.DictFactory):
    class Meta:
        model = tasks.ComputeTaskDef

    task_id = factory.Faker('uuid4')
    subtask_id = factory.Faker('uuid4')
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


class RejectReportComputedTask(factory.Factory):
    class Meta:
        model = concents.RejectReportComputedTask

    reason = factory.Faker(
        'random_element',
        elements=concents.RejectReportComputedTask.REASON,
    )
    subtask_id = factory.Faker('uuid4')
    task_to_compute = factory.SubFactory(
        TaskToCompute,
        compute_task_def__subtask_id=factory.SelfAttribute('...subtask_id'),
    )
    task_failure = factory.SubFactory(
        TaskFailure,
        task_to_compute=factory.SelfAttribute(
            '..task_to_compute',
        )
    )
    cannot_compute_task = factory.SubFactory(
        CannotComputeTask,
        task_to_compute=factory.SelfAttribute(
            '..task_to_compute',
        )
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


class ForceReportComputedTaskResponse(factory.Factory):
    class Meta:
        model = concents.ForceReportComputedTaskResponse

    reason = factory.Faker(
        'random_element',
        elements=concents.ForceReportComputedTaskResponse.REASON,
    )
    reject_report_computed_task = factory.SubFactory(RejectReportComputedTask)
    ack_report_computed_task = factory.SubFactory(
        AckReportComputedTask,
        subtask_id=factory.SelfAttribute(
            '..reject_report_computed_task.subtask_id',
        ),
        task_to_compute=factory.SelfAttribute(
            '..reject_report_computed_task.task_to_compute',
        ),
    )


class ForceGetTaskResultFailed(factory.Factory):
    class Meta:
        model = concents.ForceGetTaskResultFailed

    task_to_compute = factory.SubFactory(TaskToCompute)


class ForceGetTaskResult(factory.Factory):
    class Meta:
        model = concents.ForceGetTaskResult

    report_computed_task = factory.SubFactory(ReportComputedTask)


class ForceGetTaskResultRejected(factory.Factory):
    class Meta:
        model = concents.ForceGetTaskResultRejected

    force_get_task_result = factory.SubFactory(ForceGetTaskResult)


class AckForceGetTaskResult(factory.Factory):
    class Meta:
        model = concents.AckForceGetTaskResult

    force_get_task_result = factory.SubFactory(ForceGetTaskResult)
