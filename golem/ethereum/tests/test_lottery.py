import unittest
from os import urandom

from ethereum import tester
tester.serpent = True  # tester tries to load serpent module, prevent that.
from rlp.utils import decode_hex
from ethereum.utils import int_to_big_endian, denoms, sha3, zpad

try:
    from golem.ethereum.contracts import Lottery as LotteryContract
except ImportError:
    from Lottery import Lottery as LotteryContract

eth = denoms.ether


class Lottery(object):
    class Ticket:
        def __init__(self, address, begin, length):
            assert length != 0
            self.address = address
            self.begin = begin
            self.length = length
            self.node = None

    class Node:
        def __init__(self, left=None, right=None, value=None):
            self.parent = None
            if value:
                begin = zpad(int_to_big_endian(value.begin), 4)
                assert len(begin) == 4
                length = zpad(int_to_big_endian(value.length), 4)
                assert len(length) == 4
                data = value.address + begin + length
                assert len(data) == 20 + 4 + 4
                self.hash = sha3(data)
                self.value = value
                self.value.node = self
            else:
                xor = b''.join(chr(ord(a) ^ ord(b)) for a, b in zip(left.hash, right.hash))
                self.hash = sha3(xor)
                self.left = left
                self.right = right
                self.left.parent = self
                self.right.parent = self

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

    def find_winner(self, rand):
        proof = []
        for t in self.tickets:
            if rand < t.begin + t.length:
                n = t.node
                # first hash is a sibling
                while n.parent:
                    p = n.parent
                    proof.append(p.right.hash if p.left == n else p.left.hash)
                    n = p

                return t, proof

    def _print_tree(self):
        q = [self.root]
        while q:
            node = q.pop(0)
            print("*", node.hash.encode('hex'),
                  node.parent.hash.encode('hex')[:6] if node.parent else "")
            if hasattr(node, "value"):
                v = node.value
                print("  [{:.2}, {:.2}] {} {}"
                      .format(v.begin / float(2**32),
                              (v.begin + v.length - 1) / float(2**32),
                              v.length, v.address.encode('hex')))
            else:
                q.extend((node.left, node.right))


def validate_proof(lottery, ticket, proof):
    start = zpad(int_to_big_endian(ticket.begin), 4)
    assert len(start) == 4

    length = zpad(int_to_big_endian(ticket.length), 4)
    assert len(length) == 4

    h = sha3(ticket.address + start + length)
    assert h == ticket.node.hash

    for p in proof:
        xor = b''.join(chr(ord(a) ^ ord(b)) for a, b in zip(h, p))
        h = sha3(xor)
    assert h == lottery.root.hash

    h = sha3(lottery.nonce + h)
    assert h == lottery.hash


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
        payer_deposit = lottery.value / 10
        v = lottery.value + payer_deposit
        m = self.monitor(addr_idx, v)
        self.c.init(lottery.hash, value=v, sender=m.key)
        return m.gas()

    def lottery_get_value(self, lottery):
        return self.c.getValue(lottery.hash, sender=tester.k9)

    def lottery_get_maturity(self, lottery):
        return self.c.getMaturity(lottery.hash, sender=tester.k9)

    def lottery_get_rand(self, lottery):
        return self.c.getRandomValue(lottery.hash, sender=tester.k9)

    def lottery_randomise(self, addr_idx, lottery, deposit=0):
        m = self.monitor(addr_idx, -deposit)
        self.c.randomize(lottery.hash, value=0, sender=m.key)
        return m.gas()

    def lottery_payout(self, addr_idx, lottery, rand):
        ticket, proof = lottery.find_winner(rand)
        m = self.monitor(addr_idx)
        self.c.check(lottery.hash, lottery.nonce,
                     ticket.address, ticket.begin, ticket.length, proof, sender=tester.keys[addr_idx])
        return m.gas()

    def lottery_get_owner_deposit(self):
        return self.c.getOwnerDeposit()

    def lottery_owner_payout(self):
        return self.c.payout()

    def test_deployment(self):
        c, g = self.deploy_contract(9)
        assert len(c) == 20
        assert g <= 730736

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

        assert lottery.root.hash.encode('hex') == '033978b28985c7e15b104b1c123511ae240b6a5cec8f07e718dcedc21e1067d7'

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

        assert lottery.root.hash.encode('hex') == 'a4a2fe70f894005badf01e06726c770f100f0969c491b065ef252f5ea48b87df'

    def test_lottery_init(self):
        self.deploy_contract()
        lottery = Lottery({tester.a1: 9, tester.a2: 1})
        g = self.lottery_init(2, lottery)
        assert g <= 84103
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
        r = zpad(int_to_big_endian(r), 4)
        assert r == self.state.block.get_parent().hash[-4:]
        assert self.lottery_get_maturity(lottery) == 0
        assert self.lottery_get_value(lottery) == lottery.value

    def test_lottery_payer_deposit(self):
        self.deploy_contract()
        payer = tester.a6
        w0 = self.state.block.get_balance(payer)
        lottery = Lottery({tester.a1: 33 * eth, tester.a2: 17 * eth})
        g1 = self.lottery_init(6, lottery)
        v = 50 * eth
        deposit = v / 10
        assert self.lottery_get_value(lottery) == v
        assert self.lottery_get_maturity(lottery) == 10
        b = self.state.block.get_balance(payer) - w0
        assert b == -(v + deposit + g1)
        self.state.mine(11)
        expected_rand = self.state.block.get_parent().hash[-4:]
        self.state.mine(127)
        self.lottery_randomise(9, lottery)  # Payer gets the deposit
        r = self.lottery_get_rand(lottery)
        r = zpad(int_to_big_endian(r), 4)
        assert r == expected_rand
        b = self.state.block.get_balance(payer) - w0
        assert b == -(v + g1)

    def test_lottery_payer_deposit_sender(self):
        self.deploy_contract()
        payer = tester.a6
        w0 = self.state.block.get_balance(payer)
        lottery = Lottery({tester.a1: 11 * eth, tester.a2: 39 * eth})
        g1 = self.lottery_init(6, lottery)
        v = 50 * eth
        deposit = v / 10
        assert self.lottery_get_value(lottery) == v
        assert self.lottery_get_maturity(lottery) == 10
        b = self.state.block.get_balance(payer) - w0
        assert b == -(v + deposit + g1)
        self.state.mine(11)
        expected_rand = self.state.block.get_parent().hash[-4:]
        self.state.mine(255)
        s0 = self.state.block.get_balance(tester.a8)
        # Sender gets the deposit
        g2 = self.lottery_randomise(8, lottery, deposit)
        assert g2 > 0 and g2 <= 32000
        r = self.lottery_get_rand(lottery)
        r = zpad(int_to_big_endian(r), 4)
        assert r == expected_rand
        b = self.state.block.get_balance(payer) - w0
        assert b == -(v + deposit + g1)
        s = self.state.block.get_balance(tester.a8) - s0
        assert s == deposit - g2

    def test_lottery_payer_deposit_owner(self):
        self.deploy_contract(9)
        payer = tester.a6
        w0 = self.state.block.get_balance(payer)
        lottery = Lottery({tester.a1: 11 * eth, tester.a2: 39 * eth})
        g1 = self.lottery_init(6, lottery)
        v = 50 * eth
        deposit = v / 10
        assert self.lottery_get_value(lottery) == v
        assert self.lottery_get_maturity(lottery) == 10
        b = self.state.block.get_balance(payer) - w0
        assert b == -(v + deposit + g1)
        self.state.mine(256 + 11)
        expected_rand = self.state.block.get_parent().hash[-4:]
        # Owner gets the deposit
        self.lottery_randomise(8, lottery)
        r = self.lottery_get_rand(lottery)
        r = zpad(int_to_big_endian(r), 4)
        assert r == expected_rand
        assert b == -(v + deposit + g1)

        assert self.lottery_get_owner_deposit() == deposit

        b0 = self.state.block.get_balance(tester.a9)
        self.lottery_owner_payout()
        b = self.state.block.get_balance(tester.a9) - b0
        assert b == deposit
        assert self.lottery_get_owner_deposit() == 0

    def test_lottery_find_winner(self):
        lottery = Lottery({tester.a1: 50, tester.a2: 50})
        r = 2**32/2
        assert lottery.find_winner(r - 1)[0].address == tester.a1
        assert lottery.find_winner(r)[0].address == tester.a2

    def test_lottery_find_winner2(self):
        lottery = Lottery({
            tester.a4: 40 * eth,
            tester.a3: 30 * eth,
            tester.a2: 20 * eth,
            tester.a1: 10 * eth,
        })
        r = int(2**32 * 0.4)
        assert lottery.find_winner(r)[0].address == tester.a3

    def test_lottery_payout(self):
        self.deploy_contract()
        lottery = Lottery({
            tester.a4: 40 * eth,
            tester.a3: 30 * eth,
            tester.a2: 20 * eth,
            tester.a1: 10 * eth,
        })
        self.lottery_init(5, lottery)
        self.state.mine(100)
        self.lottery_randomise(5, lottery)
        self.state.mine(1)
        self.lottery_get_value(lottery) != 0

        lottery._print_tree()

        r = self.lottery_get_rand(lottery)
        assert r != 0
        winner, proof = lottery.find_winner(r)
        validate_proof(lottery, winner, proof)
        assert winner.address in (tester.a1, tester.a2, tester.a3, tester.a4)
        w0 = self.state.block.get_balance(winner.address)
        g = self.lottery_payout(5, lottery, r)
        assert g <= 50000
        win = self.state.block.get_balance(winner.address) - w0
        assert win == lottery.value
