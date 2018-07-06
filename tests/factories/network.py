# pylint: disable=too-few-public-methods
import faker
import factory

from golem.network.transport import native

fake = faker.Faker()


class NativeNetwork(factory.Factory):
    class Meta:
        model = native.NativeNetwork

    use_ipv6 = False
