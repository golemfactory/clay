from modelbase import BasicModel


class BasePaymentModel(BasicModel):
    def __init__(self, cliid, sessid, addr, value):
        super(BasePaymentModel, self).__init__(self.TYPE, cliid, sessid)
        self.addr = addr
        self.value = value


class ExpenditureModel(BasePaymentModel):
    TYPE = "Expense"


class IncomeModel(BasePaymentModel):
    TYPE = "Income"
