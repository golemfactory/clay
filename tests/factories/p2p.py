import faker
import factory

from golem.network.p2p.node import Node

fake = faker.Faker()


class Node(factory.Factory):
    class Meta:
        model = Node

    node_name = factory.Faker('name')
    key = factory.LazyAttribute(lambda o: format(fake.pyint(), '02x'))
