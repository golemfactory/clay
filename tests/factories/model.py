import factory

from golem_messages.factories.datastructures import p2p as p2p_factory

from golem import model


class Income(factory.Factory):
    class Meta:
        model = model.Income

    sender_node = '0xadbeef' + 'deadbeef' * 15
    payer_address = '0x' + 40 * '3'
    subtask = factory.Faker('uuid4')
    value = factory.Faker('random_int', min=1, max=10 << 20)


class CachedNode(factory.Factory):
    class Meta:
        model = model.CachedNode

    node = factory.LazyAttribute(lambda o: o.node_field.key)
    node_field = factory.SubFactory(p2p_factory.Node)


class WalletOperation(factory.Factory):
    class Meta:
        model = model.WalletOperation

    direction = factory.fuzzy.FuzzyChoice(model.WalletOperation.DIRECTION)
    operation_type = factory.fuzzy.FuzzyChoice(model.WalletOperation.TYPE)
    sender_address = '0x' + 40 * '3'
    recipient_address = '0x' + 40 * '4'
    amount = factory.fuzzy.FuzzyInteger(1, 10 << 20)
    currency = factory.fuzzy.FuzzyChoice(model.WalletOperation.CURRENCY)


class TaskPayment(factory.Factory):
    class Meta:
        model = model.TaskPayment

    wallet_operation = factory.SubFactory(
        WalletOperation,
        status=model.WalletOperation.STATUS.awaiting,
    )
    node = '0xadbeef' + 'deadbeef' * 15
    task = factory.Faker('uuid4')
    subtask = factory.Faker('uuid4')
    expected_amount = factory.fuzzy.FuzzyInteger(1, 10 << 20)
