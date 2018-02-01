# pylint: disable=too-few-public-methods
import faker
import factory

from golem.network.p2p import node

fake = faker.Faker()


class Node(factory.Factory):
    class Meta:
        model = node.Node

    node_name = factory.Faker('name')
    key = factory.LazyAttribute(lambda o: format(fake.pyint(), '02x'))  # noqa pylint: disable=no-member
