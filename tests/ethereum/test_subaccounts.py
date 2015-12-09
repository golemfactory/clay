import unittest
from ethereum import tester
tester.serpent = True  # tester tries to load serpent module, prevent that.
from rlp.utils import decode_hex, encode_hex
from ethereum.utils import int_to_big_endian, denoms

# Contract code:
# https://chriseth.github.io/browser-solidity/?gist=ac140b941584ca36be92
contract_init_hexcode = "6060604052610653806100126000396000f36060604052361561007f576000357c0100000000000000000000000000000000000000000000000000000000900480632e1a7d4d1461008157806370a0823114610099578063853828b6146100c557806390a2005b146100d4578063b69ef8a8146100f7578063d0e30db01461011a578063eddfe116146101295761007f565b005b6100976004808035906020019091905050610439565b005b6100af60048080359060200190919050506102e6565b6040518082815260200191505060405180910390f35b6100d2600480505061039f565b005b6100f56004808035906020019082018035906020019190919290505061014c565b005b6101046004805050610324565b6040518082815260200191505060405180910390f35b6101276004805050610360565b005b61014a600480803590602001908201803590602001919091929050506104f0565b005b600060006000600060006000600060005060003373ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000206000505495508534019450600093505b8787905084101561029d578787858181101561000257905090906020020135925082600190049150740100000000000000000000000000000000000000008360019004049050848111156101e75761029d565b80600060005060008473ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600082828250540192505081905550808503945084508173ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a35b8360010193508350610194565b85851415156102db5784600060005060003373ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600050819055505b5b5050505050505050565b6000600060005060008373ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060005054905061031f565b919050565b6000600060005060003373ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060005054905061035d565b90565b34600060005060003373ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000206000828282505401925050819055505b565b3373ffffffffffffffffffffffffffffffffffffffff166000600060005060003373ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060005054604051809050600060405180830381858888f19350505050506000600060005060003373ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600050819055505b565b6000600060005060003373ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060005054905081811015156104eb573373ffffffffffffffffffffffffffffffffffffffff16600083604051809050600060405180830381858888f19350505050156104ea5781600060005060003373ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000206000828282505403925050819055505b5b5b5050565b60006000600060006000349450600093505b86869050841015610603578686858181101561000257905090906020020135925082915074010000000000000000000000000000000000000000830490508481111561054d57610603565b80600060005060008473ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600082828250540192505081905550808503945084508173ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a35b8360010193508350610502565b60008511156106495784600060005060003373ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000206000828282505401925050819055505b5b5050505050505056"
contract_abi = """[{"constant":false,"inputs":[{"name":"value","type":"uint256"}],"name":"withdraw","outputs":[],"type":"function"},{"constant":true,"inputs":[{"name":"addr","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[],"name":"withdrawAll","outputs":[],"type":"function"},{"constant":false,"inputs":[{"name":"payments","type":"bytes32[]"}],"name":"transfer","outputs":[],"type":"function"},{"constant":true,"inputs":[],"name":"balance","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[],"name":"deposit","outputs":[],"type":"function"},{"constant":false,"inputs":[{"name":"payments","type":"uint256[]"}],"name":"transferExt","outputs":[],"type":"function"},{"anonymous":false,"inputs":[{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]"""

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

    def transfer(self, addr_idx, payments, value=0):
        args = []
        vsum = 0L
        for idx, v in payments:
            addr = tester.accounts[idx]
            vsum += v
            v = long(v)
            assert v < 2**96
            vv = int_to_big_endian(v)
            if len(vv) < 12:
                vv = '\0' * (12 - len(vv)) + vv
            mix = vv + addr
            assert len(mix) == 32
            print encode_hex(mix), "v: ", v, "addr", encode_hex(addr)
            args.append(mix)

        sender = self.monitor(addr_idx, vsum)
        return self.c.transfer(args, sender=sender.key, value=value)

    def test_deployment(self):
        c, g = self.deploy_contract()
        assert len(c) == 20
        assert g == 445318

    def test_create_account(self):
        self.deploy_contract()
        g = self.deposit(1, 1)
        assert g == 41396 + 4 * 68
        assert self.contract_balance() == 1

    def test_deposit(self):
        self.deploy_contract()
        self.deposit(1, 1)
        g = self.deposit(1, 10*9)
        assert g == 26396 + 4 * 68
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
        assert eg == 12324
        assert self.contract_balance() == v - w
        diff = self.state.block.get_balance(a) - b0
        cost = diff - w
        g = 21000 + 5000 + 6700 + 1472
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
