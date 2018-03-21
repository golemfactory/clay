from .modelbase import BasicModel
from .nodemetadatamodel import NodeMetadataModel


# pylint: disable-msg=too-few-public-methods
class BalanceModel(BasicModel):

    def __init__(self, meta_data: NodeMetadataModel, eth_balance: int,
                 gnt_balance: int, gntb_balance: int) -> None:
        super(BalanceModel, self).__init__(
            "Balance",
            meta_data.cliid,
            meta_data.sessid
        )
        self.eth_balance = eth_balance
        self.gnt_balance = gnt_balance
        self.gntb_balance = gntb_balance
