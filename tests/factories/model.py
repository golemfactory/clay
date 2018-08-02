from factory import Factory, Faker, SubFactory

from golem import model
from . import p2p
# pylint: disable=too-few-public-methods


class Income(Factory):
    class Meta:
        model = model.Income

    payer_address = '0x' + 40 * '3'
    subtask = Faker('uuid4')
    value = Faker('pyint')


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
