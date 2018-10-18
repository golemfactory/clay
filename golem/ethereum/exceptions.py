from ethereum.utils import denoms
import golem_sci.structs


class EthereumError(Exception):
    pass


class NotEnoughFunds(EthereumError):
    def __init__(self, required: int, available: int, extension="GNT") -> None:
        super().__init__()
        self.required = required
        self.available = available
        self.extension = extension

    def __str__(self):
        return "Not enough %s available. Required: %f, available: %f" % \
               (self.extension,
                self.required / denoms.ether,
                self.available / denoms.ether)


class TransactionError(EthereumError):
    def __init__(
            self,
            *args,
            transaction_receipt: golem_sci.structs.TransactionReceipt) -> None:
        super().__init__(*args)
        self.transaction_receipt = transaction_receipt

    def __str__(self):
        return "{parent} receipt={receipt}".format(
            parent=super().__str__(),
            receipt=self.transaction_receipt,
        )


class DepositError(TransactionError):
    pass


class LongTransactionTime(EthereumError):
    pass
