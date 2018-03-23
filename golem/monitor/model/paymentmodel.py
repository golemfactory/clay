from .modelbase import BasicModel


class BasePaymentModel(BasicModel):
    TYPE = "Payment"

    def __init__(self, sessid, addr, value):
        super(BasePaymentModel, self).__init__(self.TYPE, sessid)
        self.addr = addr
        self.value = value


class ExpenditureModel(BasePaymentModel):
    TYPE = "Expense"


class IncomeModel(BasePaymentModel):
    TYPE = "Income"
