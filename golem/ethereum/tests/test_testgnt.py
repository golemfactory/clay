import unittest
from os import urandom
from ethereum import tester
from rlp.utils import decode_hex, encode_hex
from ethereum.utils import int_to_big_endian, zpad
from golem.ethereum.contracts import TestGNT


class TestGNTTest(unittest.TestCase):
    def setUp(self):
        self.state = tester.state()

    def deploy_contract(self):
        addr = self.state.evm(decode_hex(TestGNT.INIT_HEX))
        self.state.mine()
        return tester.ABIContract(self.state, TestGNT.ABI, addr)

    @staticmethod
    def encode_payments(payments):
        args = []
        value_sum = 0L
        for idx, v in payments:
            addr = tester.accounts[idx]
            value_sum += v
            v = long(v)
            assert v < 2**96
            vv = zpad(int_to_big_endian(v), 12)
            mix = vv + addr
            assert len(mix) == 32
            print encode_hex(mix), "v: ", v, "addr", encode_hex(addr)
            args.append(mix)
        return args, value_sum

    def test_balance0(self):
        gnt = self.deploy_contract()
        b = gnt.balanceOf('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
        assert b == 0

    def test_create(self):
        gnt = self.deploy_contract()

        assert gnt.totalSupply() == 0
        gnt.create(sender=tester.k0)
        assert gnt.balanceOf(tester.a0) == 1000 * 10**18
        assert gnt.totalSupply() == 1000 * 10**18

    def test_transfer(self):
        gnt = self.deploy_contract()
        gnt.create(sender=tester.k1)
        addr = urandom(20).encode('hex')
        value = 999 * 10**18
        gnt.transfer(addr, value, sender=tester.k1)
        assert gnt.balanceOf(addr) == value

    def test_batch_transfer(self):
        gnt = self.deploy_contract()
        gnt.create(sender=tester.k0)
        payments, v = self.encode_payments([(1, 1), (2, 2), (3, 3), (4, 4)])
        gnt.batchTransfer(payments, sender=tester.k0)
        assert gnt.balanceOf(tester.a1) == 1
        assert gnt.balanceOf(tester.a2) == 2
        assert gnt.balanceOf(tester.a3) == 3
        assert gnt.balanceOf(tester.a4) == 4
        assert gnt.balanceOf(tester.a0) == 1000 * 10**18 - v
