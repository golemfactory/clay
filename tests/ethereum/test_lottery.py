import unittest
from os import urandom

from ethereum import tester
tester.serpent = True  # tester tries to load serpent module, prevent that.
from rlp.utils import decode_hex
from ethereum.utils import int_to_big_endian, denoms, sha3

from golem.ethereum.contracts import Lottery as LotteryContract

eth = denoms.ether


class Lottery(object):
    class Ticket:
        def __init__(self, address, begin, length):
            assert length != 0
            self.address = address
            self.begin = begin
            self.length = length

    class Node:
        def __init__(self, left=None, right=None, value=None):
            if value:
                begin = int_to_big_endian(value.begin)
                begin = b'0' * (4 - len(begin)) + begin
                assert len(begin) == 4
                length = int_to_big_endian(value.length)
                length = b'0' * (4 - len(length)) + length
                assert len(length) == 4
                self.hash = sha3(value.address + begin + length)
                self.value = value
            else:
                xor = [chr(ord(a) | ord(b)) for a, b in zip(left.hash, right.hash)]
                self.hash = sha3(xor)
                self.left = left
                self.right = right

    def __init__(self, payments):
        # Payments should be a dictionary. This is quite important to avoid
        # many entries for the same address and therefore hash colisions.
        assert len(payments) > 1
        self.value = sum(payments.itervalues())
        M = 2**32
        tickets = []
        for addr, v in payments.iteritems():
            l = v * M / self.value
            tickets.append(self.Ticket(addr, 0, l))

        tickets.sort(key=lambda n: n.length, reverse=True)

        c = 0
        for n in tickets:
            n.begin = c
            c += n.length

        if c < M:
            # Extend the smallest last range to compensate division roundings.
            assert c >= M - len(payments)
            tickets[-1].length = M - tickets[-1].begin
        assert sum(n.length for n in tickets) == M
        self.tickets = tickets

        nodes = [self.Node(value=t) for t in tickets]

        # Now we need to create a tree
        # TODO: This code needs refactoring

        # Number of nodes on first full level - a power of 2
        f = 2 ** (len(nodes).bit_length() - 1)

        # First we pack pairs of nodes starting from back (their probabilities
        # are the smallest so the proof is needed less often).
        i = -1
        while len(nodes) > f:
            nodes[i-1] = self.Node(left=nodes[i-1], right=nodes[i])
            del nodes[i]
            i -= 1

        while len(nodes) > 1:
            for i in xrange(len(nodes) / 2):
                nodes[i] = self.Node(left=nodes[i], right=nodes[i+1])
                del nodes[i+1]

        self.root = nodes[0]
        self.nonce = urandom(32)
        self.hash = sha3(self.nonce + self.root.hash)


class LotteryTest(unittest.TestCase):

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
        addr = self.state.evm(decode_hex(LotteryContract.INIT_HEX),
                              sender=owner.key)
        self.c = tester.ABIContract(self.state, LotteryContract.ABI, addr)
        return addr, owner.gas()

    def contract_balance(self):
        return self.state.block.get_balance(self.c.address)

    def lottery_init(self, addr_idx, lottery):
        m = self.monitor(addr_idx)
        payer_deposit = lottery.value / 10
        v = lottery.value + payer_deposit
        self.c.init(lottery.hash, value=v, sender=m.key)
        return m.gas()

    def lottery_get_value(self, lottery):
        return self.c.getValue(lottery.hash, sender=tester.k9)

    def lottery_get_maturity(self, lottery):
        return self.c.getMaturity(lottery.hash, sender=tester.k9)

    def lottery_get_rand(self, lottery):
        return self.c.getRandomValue(lottery.hash, sender=tester.k9)

    def lottery_randomise(self, addr_idx, lottery):
        m = self.monitor(addr_idx)
        self.c.randomize(lottery.hash, value=0, sender=m.key)
        return m.gas()

    def test_deployment(self):
        c, g = self.deploy_contract(9)
        assert len(c) == 20
        assert g <= 713635

        assert self.c.owner().decode('hex') == tester.a9
        assert self.c.ownerDeposit() == 0
        assert self.contract_balance() == 0

    def test_lottery_2(self):
        payments = {
            tester.a1: 1*eth,
            tester.a2: 1*eth,
        }

        lottery = Lottery(payments)
        assert lottery.value == 2*eth
        assert lottery.tickets[0].address == tester.a1

        assert lottery.root.left.value == lottery.tickets[0]
        assert lottery.root.right.value == lottery.tickets[1]

        assert lottery.root.hash.encode('hex') == '8db72c55e30b6e3c685f464236d4eb188d0ad2d12ad946676e640da047f4da95'

    def test_lottery_5(self):
        payments = {
            tester.a1: 1*eth,
            tester.a4: 4*eth,
            tester.a2: 2*eth,
            tester.a5: 5*eth,
            tester.a3: 3*eth,
        }

        lottery = Lottery(payments)
        assert lottery.value == 15*eth
        assert lottery.tickets[0].address == tester.a5

        assert lottery.root.left.left.value == lottery.tickets[0]
        assert lottery.root.left.right.value == lottery.tickets[1]
        assert lottery.root.right.left.value == lottery.tickets[2]
        assert lottery.root.right.right.left.value == lottery.tickets[3]
        assert lottery.root.right.right.right.value == lottery.tickets[4]

        assert lottery.root.hash.encode('hex') == '5bb0c968c380f1d55ef24f0d17274c438a2d2cb01e6314150238c6a71ac321e8'

    def test_lottery_init(self):
        self.deploy_contract()
        lottery = Lottery({tester.a1: 9, tester.a2: 1})
        g = self.lottery_init(2, lottery)
        assert g <= 84092
        assert self.lottery_get_value(lottery) == 10
        assert self.lottery_get_maturity(lottery) == 10

    def test_lottery_randomise(self):
        self.deploy_contract()
        lottery = Lottery({tester.a1: 50 * eth, tester.a2: 50 * eth})
        assert lottery.value == 100 * eth
        self.lottery_init(3, lottery)
        assert self.lottery_get_value(lottery) == lottery.value
        self.state.mine(11)
        assert self.state.block.number == 11
        assert self.state.block.number > self.lottery_get_maturity(lottery)
        r = self.lottery_get_rand(lottery)
        assert r == 0
        g = self.lottery_randomise(3, lottery)
        assert g <= 44919
        r = self.lottery_get_rand(lottery)
        assert int_to_big_endian(r) == self.state.block.get_parent().hash[-4:]
        assert self.lottery_get_maturity(lottery) == 0
        assert self.lottery_get_value(lottery) == lottery.value
