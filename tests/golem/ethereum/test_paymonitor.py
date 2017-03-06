import pytest

from ethereum.utils import zpad
from ethereum.transactions import Transaction
from golem.ethereum.paymentmonitor import log2payment

def test():
    myaddr = "86a06eab0650295dced86801cd629727dee13415".decode('hex')
    data = [{u'blockHash': None, u'transactionHash': u'0x0000000000000000000000000000000000000000000000000000000000000000', u'data': u'0x000000000000000000000000000000000000000000000000000002bd358472a4', u'topics': [u'0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef', u'0x000000000000000000000000d8f1cdc8c18dfc3cc0df10ba162b2eb8fe2a2294', u'0x00000000000000000000000086a06eab0650295dced86801cd629727dee13415'], u'blockNumber': None, u'address': u'0x689ed42ec0c3b3b799dc5659725bf536635f45d1', u'logIndex': 0, u'removed': False, u'transactionIndex': 0}]
    log2payment(data[0], myaddr)
