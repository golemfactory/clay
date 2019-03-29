# pylint: disable=too-few-public-methods
import faker
import factory

from golem.core.net import network

fake = faker.Faker()


class NativeNetwork(factory.Factory):
    class Meta:
        model = network.ProxyNetwork

    use_ipv6 = False
