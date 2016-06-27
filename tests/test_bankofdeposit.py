import unittest
from ethereum import tester
tester.serpent = True  # tester tries to load serpent module, prevent that.
from rlp.utils import decode_hex, encode_hex
from ethereum.utils import int_to_big_endian, denoms, zpad

try:
    from golem.ethereum.contracts import BankOfDeposit
except ImportError:
    from BankOfDeposit import BankOfDeposit

eth = denoms.ether


class BankContractTest(unittest.TestCase):

    class Monitor:
        def __init__(self, state, account_idx, value=0):
            self.addr = tester.accounts[account_idx]
            self.key = tester.keys[account_idx]
            self.state = state
            self.value = value
            self.initial = state.block.get_balance(self.addr)
            assert self.initial > 0
            assert self.addr != state.block.coinbase

        def gas(self):
            b = self.state.block.get_balance(self.addr)
            total = self.initial - b
            g = (total - self.value) / tester.gas_price
            return g

    def monitor(self, addr, value=0):
        return self.Monitor(self.state, addr, value)

    def setUp(self):
        self.state = tester.state()

    def deploy_contract(self, owner_idx=9):
        owner = self.monitor(owner_idx)
        addr = self.state.evm(decode_hex(BankOfDeposit.INIT_HEX),
                              sender=owner.key)
        self.c = tester.ABIContract(self.state, BankOfDeposit.ABI, addr)
        return addr, owner.gas()

    def contract_balance(self):
        return self.state.block.get_balance(self.c.address)

    def deposit(self, addr_idx, value):
        m = self.monitor(addr_idx, value)
        self.c.deposit(sender=m.key, value=value)
        return m.gas()

    def balance(self, addr_idx):
        return self.c.balance(sender=tester.keys[addr_idx])

    def balance_of(self, addr_idx):
        return self.c.balanceOf(tester.accounts[addr_idx])

    def withdraw(self, addr_idx, value, to=None):
        m = self.monitor(addr_idx)
        if to:
            to_addr = tester.accounts[to]
            o = self.c.withdraw(value, to_addr, sender=m.key, profiling=True)
        else:
            o = self.c.withdraw(value, sender=m.key, profiling=True)
        return o['gas']

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

    def transfer(self, addr_idx, payments, value=0):
        args, vsum = self.encode_payments(payments)
        sender = self.monitor(addr_idx, vsum)
        self.c.transfer(args, sender=sender.key, value=value)
        return sender.gas()

    def transfer_external_value(self, addr_idx, payments, value):
        args, vsum = self.encode_payments(payments)
        sender = self.monitor(addr_idx, vsum)
        self.c.transferExternalValue(args, sender=sender.key, value=value)
        return sender.gas()

    def test_deployment(self):
        c, g = self.deploy_contract()
        assert len(c) == 20
        assert g <= 236904

    def test_create_account(self):
        self.deploy_contract()
        g = self.deposit(1, 1)
        assert g <= 41672
        assert self.contract_balance() == 1

    def test_deposit(self):
        self.deploy_contract()
        self.deposit(1, 1)
        g = self.deposit(1, 10*9)
        assert g <= 26672
        assert self.contract_balance() == 10*9 + 1

    def test_balance(self, dep=12345678):
        self.deploy_contract()
        self.deposit(5, dep)
        assert self.balance(5) == dep
        assert self.balance_of(5) == dep

    def test_withdraw(self):
        self.deploy_contract()
        assert self.contract_balance() == 0
        v = 4800 * eth  # TODO: Use pytest parametrize
        w = 2016 * eth
        self.deposit(6, v)
        assert self.contract_balance() == v
        assert self.balance_of(6) == v
        a = tester.accounts[6]
        b0 = self.state.block.get_balance(a)
        eg = self.withdraw(6, w)
        assert eg <= 12393
        assert self.contract_balance() == v - w
        diff = self.state.block.get_balance(a) - b0
        g = w - diff
        limit = 21000 + 5000 + 6700 + 1492
        assert g <= limit
        assert self.balance_of(6) == v - w

    def test_withdraw_overlimit(self):
        self.deploy_contract()
        v = 1000 * eth
        w = 2016 * eth
        self.deposit(6, v)
        assert self.balance_of(6) == v
        a = tester.accounts[6]
        b0 = self.state.block.get_balance(a)
        with self.assertRaises(tester.TransactionFailed):
            self.withdraw(6, w)
        g = b0 - self.state.block.get_balance(a)
        assert g == 3141592  # OOG
        assert self.balance_of(6) == v

    def test_withdraw_explicit_to_self(self):
        self.deploy_contract()
        assert self.contract_balance() == 0
        v = 1234 * eth
        w = 1111 * eth
        self.deposit(6, v)
        assert self.contract_balance() == v
        assert self.balance_of(6) == v
        a = tester.accounts[6]
        b0 = self.state.block.get_balance(a)
        eg = self.withdraw(6, w, 6)
        assert eg <= 12408
        assert self.contract_balance() == v - w
        diff = self.state.block.get_balance(a) - b0
        g = w - diff
        limit = 21000 + 5000 + 6700 + 2881
        assert g <= limit
        assert self.balance_of(6) == v - w

    def test_withdraw_explicit_to(self):
        self.deploy_contract()
        assert self.contract_balance() == 0
        v = 1234 * eth
        w = 1111 * eth
        self.deposit(6, v)
        assert self.contract_balance() == v
        assert self.balance_of(6) == v
        a = tester.accounts[6]
        b0 = self.state.block.get_balance(a)
        to = tester.accounts[7]
        b_to = self.state.block.get_balance(to)
        eg = self.withdraw(6, w, 7)
        assert eg <= 12408
        assert self.contract_balance() == v - w
        g = b0 - self.state.block.get_balance(a)
        limit = 21000 + 5000 + 6700 + 2881
        assert g <= limit
        assert self.balance_of(6) == v - w
        assert self.state.block.get_balance(to) - b_to == w

    def test_transfer_2(self):
        """Deposits some money, then transfers it to 2 other accounts."""
        self.deploy_contract()
        v = 1000 * eth
        self.deposit(1, v)
        self.transfer(1, [(2, 1*eth), (3, 999*eth)])
        assert self.balance(1) == 0
        assert self.balance(2) == 1*eth
        assert self.balance(3) == 999*eth

    def test_transfer_value_4(self):
        """Transfers value included in transaction to 4 other accounts."""
        self.deploy_contract()
        self.deposit(1, 1)
        self.deposit(2, 1)
        self.deposit(3, 1)
        self.deposit(4, 1)
        self.deposit(5, 1)
        v = 1000 * eth
        g = self.transfer(1, [(2, 2*eth), (3, 3*eth), (4, 4*eth), (5, 5*eth)],
                          value=v)
        assert self.balance(2) == 2*eth + 1
        assert self.balance(3) == 3*eth + 1
        assert self.balance(4) == 4*eth + 1
        assert self.balance(5) == 5*eth + 1
        b1 = self.balance(1)
        assert b1 == (1000-2-3-4-5)*eth + 1  # Rest should go to 1
        g -= b1
        assert g <= 63032

    def test_transfer_mixed_4(self):
        """Deposits some value, then transfers bigger amount to 4 other
           accounts using deposited value and value included in transaction.
           """
        self.deploy_contract()
        v = 100
        p = 55 + 44 + 33 + 22
        d = p / 2
        self.deposit(1, d*eth)  # Deposit half of payments
        self.transfer(1, [(5, 55*eth), (4, 44*eth), (3, 33*eth), (2, 22*eth)],
                      value=(d + 100)*eth)  # Transfer another half + v
        assert self.balance(2) == 22*eth
        assert self.balance(3) == 33*eth
        assert self.balance(4) == 44*eth
        assert self.balance(5) == 55*eth
        assert self.balance(1) == v*eth  # Rest should go to 1

    def test_transfer_exact_value_2(self):
        """Transfers exact value included in transaction to 2 other accounts.
           This is a benchmark used to compare with transferExternalValue().
           See :func:test_transfer_external_value_2.
           """
        self.deploy_contract()
        self.deposit(1, 1)
        self.deposit(7, 1)
        v1, v7 = 1*eth, 7*eth
        v = v1 + v7
        g = self.transfer(8, [(1, v1), (7, v7)], value=v)
        assert g <= 39975
        assert self.balance(8) == 0
        assert self.balance(1) == v1 + 1
        assert self.balance(7) == v7 + 1
        assert self.contract_balance() == v + 2

    def test_transfer_external_value_2(self):
        """Transfers exact value included in transaction to 2 other accounts.
           This is a benchmark used to compare with transfer().
           See :func:test_transfer_exact_value_2.
           """
        self.deploy_contract()
        self.deposit(1, 1)
        self.deposit(7, 1)
        v1, v7 = 1*eth, 7*eth
        v = v1 + v7
        g = self.transfer_external_value(8, [(1, v1), (7, v7)], value=v)
        savings = 1 - (g / 39975.0)
        assert g <= 39843
        assert savings < 0.005
        assert self.balance(8) == 0
        assert self.balance(1) == v1 + 1
        assert self.balance(7) == v7 + 1
        assert self.contract_balance() == v + 2
