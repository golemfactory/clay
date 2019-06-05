from factory import (
    Factory,
    Faker,
    fuzzy,
    SubFactory,
)

from golem import model


class Income(Factory):
    class Meta:
        model = model.Income

    sender_node = '0xadbeef' + 'deadbeef' * 15
    payer_address = '0x' + 40 * '3'
    subtask = Faker('uuid4')
    value = Faker('random_int', min=1, max=10 << 20)


class WalletOperation(Factory):
    class Meta:
        model = model.WalletOperation

    direction = fuzzy.FuzzyChoice(model.WalletOperation.DIRECTION)
    operation_type = fuzzy.FuzzyChoice(model.WalletOperation.TYPE)
    sender_address = '0x' + 40 * '3'
    recipient_address = '0x' + 40 * '4'
    amount = fuzzy.FuzzyInteger(1, 10 << 20)
    currency = fuzzy.FuzzyChoice(model.WalletOperation.CURRENCY)

class TaskPayment(Factory):
    class Meta:
        model = model.TaskPayment

    wallet_operation = SubFactory(WalletOperation)
    node = '0xadbeef' + 'deadbeef' * 15
    task = Faker('uuid4')
    subtask = Faker('uuid4')
    expected_amount = fuzzy.FuzzyInteger(1, 10 << 20)
