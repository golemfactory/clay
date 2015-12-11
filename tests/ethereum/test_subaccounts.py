import unittest
from ethereum import tester
tester.serpent = True  # tester tries to load serpent module, prevent that.
from rlp.utils import decode_hex, encode_hex
from ethereum.utils import int_to_big_endian, denoms

# Contract code:
# https://chriseth.github.io/browser-solidity/?gist=ac140b941584ca36be92
contract_init_hexcode = "6060604052610656806100126000396000f36060604052361561007f576000357c0100000000000000000000000000000000000000000000000000000000900480632e1a7d4d146100815780633f883dfb1461009957806370a08231146100bc578063853828b6146100e857806390a2005b146100f7578063b69ef8a81461011a578063d0e30db01461013d5761007f565b005b6100976004808035906020019091905050610225565b005b6100ba600480803590602001908201803590602001919091929050506102d7565b005b6100d260048080359060200190919050506105dc565b6040518082815260200191505060405180910390f35b6100f5600480505061018b565b005b61011860048080359060200190820180359060200191909192905050610442565b005b610127600480505061061a565b6040518082815260200191505060405180910390f35b61014a600480505061014c565b005b34600060005060003373ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000206000828282505401925050819055505b565b3373ffffffffffffffffffffffffffffffffffffffff166000600060005060003373ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060005054604051809050600060405180830381858888f19350505050506000600060005060003373ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600050819055505b565b6000600060005060003373ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060005054905081811015156102d2573373ffffffffffffffffffffffffffffffffffffffff16600083604051809050600060405180830381858888f193505050505081600060005060003373ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000206000828282505403925050819055505b5b5050565b60006000600060006000349450600093505b868690508410156103f25786868581811015610002579050909060200201359250826001900491507401000000000000000000000000000000000000000083600190040490508481111561033c576103f2565b80600060005060008473ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600082828250540192505081905550808503945084508173ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a35b83600101935083506102e9565b60008511156104385784600060005060003373ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000206000828282505401925050819055505b5b50505050505050565b600060006000600060006000600060005060003373ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000206000505495508534019450600093505b87879050841015610593578787858181101561000257905090906020020135925082600190049150740100000000000000000000000000000000000000008360019004049050848111156104dd57610593565b80600060005060008473ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600082828250540192505081905550808503945084508173ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a35b836001019350835061048a565b85851415156105d15784600060005060003373ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600050819055505b5b5050505050505050565b6000600060005060008373ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600050549050610615565b919050565b6000600060005060003373ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600050549050610653565b9056"
contract_abi = """[{"constant":false,"inputs":[{"name":"value","type":"uint256"}],"name":"withdraw","outputs":[],"type":"function"},{"constant":false,"inputs":[{"name":"payments","type":"bytes32[]"}],"name":"transferExternalValue","outputs":[],"type":"function"},{"constant":true,"inputs":[{"name":"addr","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[],"name":"withdrawAll","outputs":[],"type":"function"},{"constant":false,"inputs":[{"name":"payments","type":"bytes32[]"}],"name":"transfer","outputs":[],"type":"function"},{"constant":true,"inputs":[],"name":"balance","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[],"name":"deposit","outputs":[],"type":"function"},{"anonymous":false,"inputs":[{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]"""

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
        addr = self.state.evm(decode_hex(contract_init_hexcode),
                              sender=owner.key)
        self.c = tester.ABIContract(self.state, contract_abi, addr)
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

    def withdraw(self, addr_idx, value):
        m = self.monitor(addr_idx)
        o = self.c.withdraw(value, sender=m.key, profiling=True)
        return o['gas'] - 21000

    @staticmethod
    def encode_payments(payments):
        args = []
        value_sum = 0L
        for idx, v in payments:
            addr = tester.accounts[idx]
            value_sum += v
            v = long(v)
            assert v < 2**96
            vv = int_to_big_endian(v)
            if len(vv) < 12:
                vv = '\0' * (12 - len(vv)) + vv
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
        assert g == 446122

    def test_create_account(self):
        self.deploy_contract()
        g = self.deposit(1, 1)
        assert g == 41690
        assert self.contract_balance() == 1

    def test_deposit(self):
        self.deploy_contract()
        self.deposit(1, 1)
        g = self.deposit(1, 10*9)
        assert g == 26690
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
        assert eg == 12309
        assert self.contract_balance() == v - w
        diff = self.state.block.get_balance(a) - b0
        cost = diff - w
        g = 21000 + 5000 + 6700 + 1457
        assert cost == -g
        assert self.balance_of(6) == v - w

    def test_withdraw_overlimit(self):
        self.deploy_contract()
        v = 1000 * eth
        w = 2016 * eth
        self.deposit(6, v)
        assert self.balance_of(6) == v
        a = tester.accounts[6]
        b0 = self.state.block.get_balance(a)
        self.withdraw(6, w)
        diff = self.state.block.get_balance(a) - b0
        g = 21000 + 1170
        assert diff == -g
        assert self.balance_of(6) == v

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
        v = 1000 * eth
        self.transfer(1, [(2, 2*eth), (3, 3*eth), (4, 4*eth), (5, 5*eth)],
                      value=v)
        assert self.balance(2) == 2*eth
        assert self.balance(3) == 3*eth
        assert self.balance(4) == 4*eth
        assert self.balance(5) == 5*eth
        assert self.balance(1) == (1000-2-3-4-5)*eth  # Rest should go to 1

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
        assert g == 40152
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
        savings = 1 - (g / 40152.0)
        assert g == 39985
        assert savings < 0.005
        assert self.balance(8) == 0
        assert self.balance(1) == v1 + 1
        assert self.balance(7) == v7 + 1
        assert self.contract_balance() == v + 2
