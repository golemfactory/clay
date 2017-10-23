import operator
import random
import unittest
import uuid

import sys

from golem.network.p2p.peerkeeper import PeerKeeper, K_SIZE, CONCURRENCY, \
    node_id_distance
from golem.utils import encode_hex


def random_key(n_bytes, prefix=None):
    prefix = prefix or bytes()
    n_bytes = n_bytes - len(prefix)
    rand = bytes(random.randint(0, 255) for _ in range(n_bytes))
    return prefix + rand


def key_to_number(key_bytes):
    return int.from_bytes(key_bytes, sys.byteorder)


class TestPeerKeeper(unittest.TestCase):

    def setUp(self):
        self.n_bytes = K_SIZE // 8
        self.key = random_key(self.n_bytes)
        self.key_num = key_to_number(self.key)
        self.peer_keeper = PeerKeeper(encode_hex(self.key))

    def test_neighbours(self):
        keys = set(random_key(self.n_bytes) for _ in range(64))
        peers = set()

        for k in keys:
            peer = MockPeer(k)
            peers.add(peer)
            self.peer_keeper.add_peer(peer)

        # Sort keys by distance to self.key
        distances = {p.key: node_id_distance(p, self.key_num) for p in peers}
        ordered = sorted(distances.items(), key=operator.itemgetter(1))
        ordered = [o[0] for o in ordered]

        # Default count
        expected_n = CONCURRENCY
        nodes = self.peer_keeper.neighbours(self.key_num)
        assert len(nodes) == expected_n
        assert all(node.key in ordered[:16] for node in nodes)

        # Desired count
        expected_n = 10
        nodes = self.peer_keeper.neighbours(self.key_num, expected_n)
        assert len(nodes) == expected_n
        assert all(node.key in ordered[:32] for node in nodes)

        nodes = self.peer_keeper.neighbours(self.key_num, 256)
        assert len(nodes) <= len(keys)


class MockPeer:
    def __init__(self, key):
        self.key = encode_hex(key)
        self.address = random.randrange(1, 2 ** 32 - 1)
        self.port = random.randrange(1000, 65535)
        self.node = None
        self.node_name = str(uuid.uuid4())

    def __str__(self):
        return self.key

    def __repr__(self):
        return str(self)
