import factory

from golem_messages.factories.datastructures import p2p as p2p_factory
from golem_messages.factories.helpers import (
    random_eth_address,
    random_eth_pub_key,
)

from golem import model


class CachedNode(factory.Factory):
    class Meta:
        model = model.CachedNode

    node = factory.LazyAttribute(lambda o: o.node_field.key)
    node_field = factory.SubFactory(p2p_factory.Node)


class WalletOperation(factory.Factory):
    class Meta:
        model = model.WalletOperation

    status = factory.fuzzy.FuzzyChoice(model.WalletOperation.STATUS)
    direction = factory.fuzzy.FuzzyChoice(model.WalletOperation.DIRECTION)
    operation_type = factory.fuzzy.FuzzyChoice(model.WalletOperation.TYPE)
    sender_address = factory.LazyFunction(random_eth_address)
    recipient_address = factory.LazyFunction(random_eth_address)
    amount = factory.fuzzy.FuzzyInteger(1, 10 << 20)
    currency = factory.fuzzy.FuzzyChoice(model.WalletOperation.CURRENCY)
    gas_cost = 0


class TaskPayment(factory.Factory):
    class Meta:
        model = model.TaskPayment

    wallet_operation = factory.SubFactory(
        WalletOperation,
    )
    node = factory.LazyFunction(random_eth_pub_key)
    task = factory.Faker('uuid4')
    subtask = factory.Faker('uuid4')
    expected_amount = factory.fuzzy.FuzzyInteger(1, 10 << 20)
