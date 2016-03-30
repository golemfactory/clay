from ethereum.utils import privtoaddr

from golem.core.keysauth import EllipticalKeysAuth, sha3
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumincomeskeeper import EthereumIncomesKeeper


class TestEthereumIncomesKeeper(TestWithDatabase):
    def test_get_income(self):
        ik = EthereumIncomesKeeper()
        e = EllipticalKeysAuth()
        node = e.get_key_id()
        self.assertIsNone(ik.get_income(node, 0))
        self.assertEqual(ik.get_income(node, 10), [])
        ik.add_waiting_payment("xyz", node, 3)
        ik.add_waiting_payment("abc", node, 2)
        ik.add_waiting_payment("qvu", "DEF", 1)
        ik.add_waiting_payment("def", node, 10)
        self.assertEqual(ik.get_income(node, 10), [])
        self.assertEqual(ik.get_income(privtoaddr(e._private_key), 10), ["xyz", "abc"])
        self.assertEqual(ik.get_income(privtoaddr(e._private_key), 2), [])
        self.assertEqual(ik.get_income(privtoaddr(e._private_key), 3), ["def"])