
import factory

from golem.task.result.resultpackage import ExtractedPackage


class ExtractedPackageFactory(factory.Factory):
    class Meta:
        model = ExtractedPackage

    files = factory.List([factory.Faker('file_name')])
