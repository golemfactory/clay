import logging

from ethereum.utils import normalize_address


from golem.utils import encode_hex

logger = logging.getLogger(__name__)


class EthAccountInfo(object):
    """ Information about node's payment account and Ethereum account. """
    def __init__(self, key_id, node_name, node_info, eth_account):
        self.key_id = key_id
        self.node_name = node_name
        self.node_info = node_info
        self.eth_account = EthereumAddress(eth_account)

    def __eq__(self, other):
        ethereum_eq = self.eth_account == other.eth_account
        account_eq = self.key_id == other.key_id

        return ethereum_eq and account_eq


class EthereumAddress(object):
    """ Keeps information about ethereum addresses in normalized format
    """

    @classmethod
    def __parse(cls, address):
        if len(address) in range(40, 51):
            address = address.lower()
        return normalize_address(address)

    def __init__(self, address):
        self.address = None
        if address:  # Try parsing address only if not null
            try:
                self.address = self.__parse(address)
            except Exception as err:
                logger.warning("Invalid Ethereum address '{}', parse error: {}"
                               .format(address, err))

    def get_str_addr(self):
        if self.address:
            return "0x{}".format(encode_hex(self.address))
        return None

    def __eq__(self, other):
        return self.address == other.address

    def __bool__(self):
        return self.address is not None
