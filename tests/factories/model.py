from factory import Factory, Faker, SubFactory

from golem_messages.factories.datastructures import p2p
from golem import model


class Income(Factory):
    class Meta:
        model = model.Income

    sender_node = '00adbeef' + 'deadbeef' * 15
    payer_address = '0x' + 40 * '3'
    subtask = Faker('uuid4')
    value = Faker('random_int', min=1, max=10 << 20)


class PaymentDetails(Factory):
    class Meta:
        model = model.PaymentDetails

    node_info = SubFactory(p2p.Node)
    fee = Faker('pyint')


class Payment(Factory):
    class Meta:
        model = model.Payment

    subtask = Faker('uuid4')
    payee = Faker('binary', length=20)
    value = Faker('pyint')
    details = SubFactory(PaymentDetails)
