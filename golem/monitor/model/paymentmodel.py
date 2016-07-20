from modelbase import BasicModel


class PaymentModel(BasicModel):

    # payment_infos == list({'addr': str, 'value': int})
    def __init__(self, payment_infos):
        super(PaymentModel, self).__init__("Payment")

        self.payment_infos = payment_infos


class IncomeModel(BasicModel):

    def __init__(self, addr, value):
        super(IncomeModel, self).__init__("Income")

        self.addr = addr
        self.value = value
