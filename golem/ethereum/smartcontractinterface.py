from typing import Any, Dict, List, Optional
from ethereum.transactions import Transaction


class SmartContractInterface(object):
    def __init__(self, geth_client, token):
        self.GAS_PRICE = token.GAS_PRICE
        self.GAS_PER_PAYMENT = token.GAS_PER_PAYMENT
        self.GAS_BATCH_PAYMENT_BASE = token.GAS_BATCH_PAYMENT_BASE
        self._geth_client = geth_client
        self._token = token

    def get_eth_balance(self, address: str) -> Optional[int]:
        """
        Returns None is case of issues coming from the geth client
        """
        return self._geth_client.get_balance(address)

    def get_gnt_balance(self, address: str) -> Optional[int]:
        return self._token.get_gnt_balance(address)

    def get_gntw_balance(self, address: str) -> Optional[int]:
        return self._token.get_gntw_balance(address)

    def prepare_batch_transfer(self,
                               privkey: bytes,
                               payments,
                               closure_time: int) -> Transaction:
        return self._token.batch_transfer(privkey, payments, closure_time)

    def send_transaction(self, tx: Transaction):
        return self._geth_client.send(tx)

    def get_block_number(self) -> int:
        return self._geth_client.get_block_number()

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        return self._geth_client.get_transaction_receipt(tx_hash)

    def get_incomes_from_block(self, block: int, address: str) -> List[Any]:
        return self._token.get_incomes_from_block(block, address)

    def request_gnt_from_faucet(self, privkey: bytes) -> None:
        self._token.request_from_faucet(privkey)

    def stop(self) -> None:
        self._geth_client._kill_node()

    def wait_until_synchronized(self) -> bool:
        return self._geth_client.wait_until_synchronized()

    def is_synchronized(self) -> bool:
        return self._geth_client.is_synchronized()
