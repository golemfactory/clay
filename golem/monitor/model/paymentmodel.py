from modelbase import BasicModel


class PaymentModel(BasicModel):

    def __init__(self, cliid, sessid, payment_infos):
        super(PaymentModel, self).__init__("Payment", cliid, sessid)

        self.payment_infos = payment_infos


class IncomeModel(BasicModel):

    def __init__(self, cliid, sessid, addr, value):
        super(IncomeModel, self).__init__("Income", cliid, sessid)

        self.addr = addr
        self.value = value
