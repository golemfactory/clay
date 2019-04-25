import typing

from ethereum.utils import denoms
import golem_sci.structs


class EthereumError(Exception):
    def to_dict(self) -> dict:
        return {
            'error_type': self.__class__.__name__,
            'error_msg': self.__str__(),
            'error_details': {}
        }


class MissingFunds(typing.NamedTuple):
    """
    Represents a single entry for missing funds in a given currency.
    """
    required: int
    available: int
    extension: str


class NotEnoughFunds(EthereumError):
    def __init__(
            self,
            missing_funds: typing.Optional[typing.List[MissingFunds]] = None,
            required: int = -1,
            available: int = -1,
            extension: str = '') -> None:
        super().__init__()
        if not missing_funds:
            self.missing_funds = [
                MissingFunds(
                    required=required,
                    available=available,
                    extension=extension
                )
            ]
        else:
            self.missing_funds = missing_funds

    def __str__(self) -> str:
        return "Not enough funds available." + self._missing_funds_to_str()

    def to_dict(self) -> dict:
        err_dict = super().to_dict()
        err_dict['error_details']['missing_funds'] = \
            [entry._asdict() for entry in self.missing_funds]

        return err_dict

    def _missing_funds_to_str(self) -> str:
        res = ""
        for required, available, extension in self.missing_funds:
            res += f"\nRequired {extension}: {required / denoms.ether:f}, " \
                f"available: {available / denoms.ether:f}"

        return res


class NotEnoughDepositFunds(NotEnoughFunds):
    def __str__(self) -> str:
        return "Not enough funds for Concent deposit." \
               "Top up your account or create the task with Concent disabled." \
               + self._missing_funds_to_str()


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


class ContractUnavailable(EthereumError):
    pass


class LongTransactionTime(EthereumError):
    pass
