
import factory

from golem.task.result.resultpackage import (
    ExtractedPackage, TaskResultDescriptor
)

from .taskserver import WaitingTaskResultFactory


class TaskResultDescriptorFactory(factory.Factory):
    class Meta:
        model = TaskResultDescriptor

    task_result = factory.SubFactory(WaitingTaskResultFactory)


class ExtractedPackageFactory(factory.Factory):
    class Meta:
        model = ExtractedPackage

    files = factory.List([factory.Faker('file_name')])
    descriptor = factory.SubFactory(TaskResultDescriptorFactory)
