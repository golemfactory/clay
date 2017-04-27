from ethereum.utils import privtoaddr

from golem import testutils
from golem.core.keysauth import EllipticalKeysAuth, sha3
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumincomeskeeper import EthereumIncomesKeeper


class TestEthereumIncomesKeeper(TestWithDatabase, testutils.PEP8MixIn):
    PEP8_FILES = ['golem/transactions/ethereum/ethereumincomeskeeper.py', ]
