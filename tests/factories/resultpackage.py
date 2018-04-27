# pylint: disable=too-few-public-methods
import factory

from golem.task.result.resultpackage import (
    ExtractedPackage, TaskResultDescriptor
)

from . import p2p as p2p_factory
from .taskserver import WaitingTaskResultFactory


class TaskResultDescriptorFactory(factory.Factory):
    class Meta:
        model = TaskResultDescriptor

    node = p2p_factory.Node()
    task_result = factory.SubFactory(WaitingTaskResultFactory)


class ExtractedPackageFactory(factory.Factory):
    class Meta:
        model = ExtractedPackage

    files = factory.List([factory.Faker('file_name')])
    descriptor = factory.SubFactory(TaskResultDescriptorFactory)
