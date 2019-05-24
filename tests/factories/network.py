# pylint: disable=too-few-public-methods
import faker
import factory

from golem.core.net import network

fake = faker.Faker()


class NativeNetwork(factory.Factory):
    class Meta:
        model = network.LibP2PNetwork

    use_ipv6 = False
