# pylint: disable=too-few-public-methods
import faker
import factory

from golem.network.p2p import node

fake = faker.Faker()


class Node(factory.Factory):
    class Meta:
        model = node.Node

    node_name = factory.Faker('name')
    # considered as difficult by `keysauth.is_pubkey_difficult` with level 10
    key = '00adbeef' + 'deadbeef' * 15
