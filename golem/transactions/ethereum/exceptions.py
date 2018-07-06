from ethereum.utils import denoms


class EthereumError(Exception):
    pass


class NotEnoughFunds(EthereumError):
    def __init__(self, required: int, available: int, extension="GNT"):
        super().__init__()
        self.required = required
        self.available = available
        self.extension = extension

    def __str__(self):
        return "Not enough %s available. Required: %f, available: %f" % \
               (self.extension,
                self.required / denoms.ether,
                self.available / denoms.ether)
