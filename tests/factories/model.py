import factory

from golem_messages.factories.datastructures import p2p
from golem import model


class Income(factory.Factory):
    class Meta:
        model = model.Income

    sender_node = '00adbeef' + 'deadbeef' * 15
    payer_address = '0x' + 40 * '3'
    subtask = factory.Faker('uuid4')
    value = factory.Faker('random_int', min=1, max=10 << 20)


class PaymentDetails(factory.Factory):
    class Meta:
        model = model.PaymentDetails

    node_info = factory.SubFactory(p2p.Node)
    fee = factory.Faker('pyint')


class Payment(factory.Factory):
    class Meta:
        model = model.Payment

    subtask = factory.Faker('uuid4')
    payee = factory.Faker('binary', length=20)
    value = factory.Faker('pyint')
    details = factory.SubFactory(PaymentDetails)


class CachedNode(factory.Factory):
    class Meta:
        model = model.CachedNode

    node = factory.LazyAttribute(lambda o: o.node_field.key)
    node_field = factory.SubFactory(p2p.Node)
