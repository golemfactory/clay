import operator
import random
import sys
import unittest
import uuid

from golem_messages.factories.datastructures import p2p as dt_p2p_factory

from eth_utils import encode_hex
from golem.network.p2p.peerkeeper import PeerKeeper, K_SIZE, CONCURRENCY, \
    node_id_distance
from golem import testutils


def random_key(n_bytes, prefix=None):
    prefix = prefix or bytes()
    n_bytes = n_bytes - len(prefix)
    rand = bytes(random.randint(0, 255) for _ in range(n_bytes))
    return prefix + rand


def key_to_number(key_bytes):
    return int.from_bytes(key_bytes, sys.byteorder)


def is_sorted_by_distance(peers, key_num):
    def dist(peer):
        return node_id_distance(peer, key_num)
    for i in range(len(peers)-1):
        if dist(peers[i]) > dist(peers[i+1]):
            return False
    return True


class TestPeerKeeper(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['golem/network/p2p/peerkeeper.py']

    def setUp(self):
        self.n_bytes = K_SIZE // 8
        self.key = random_key(self.n_bytes)
        self.key_num = key_to_number(self.key)
        self.peer_keeper = PeerKeeper(encode_hex(self.key)[2:])

    def test_neighbours(self):
        keys = set(random_key(self.n_bytes) for _ in range(64))
        peers = set()

        for k in keys:
            peer = MockPeer(k)
            if self.peer_keeper.add_peer(peer) is None:
                peers.add(peer)

        # Sort keys by distance to self.key
        distances = {p.key: node_id_distance(p, self.key_num) for p in peers}
        ordered = sorted(distances.items(), key=operator.itemgetter(1))
        ordered = [o[0] for o in ordered]

        # Default count
        expected_n = CONCURRENCY
        nodes = self.peer_keeper.neighbours(self.key_num)
        assert len(nodes) == expected_n
        assert is_sorted_by_distance(nodes, self.key_num)
        assert all(node.key in ordered[:expected_n] for node in nodes)

        # Desired count
        expected_n = 10
        nodes = self.peer_keeper.neighbours(self.key_num, expected_n)
        assert len(nodes) == expected_n
        assert is_sorted_by_distance(nodes, self.key_num)
        assert all(node.key in ordered[:expected_n] for node in nodes)

        nodes = self.peer_keeper.neighbours(self.key_num, 256)
        assert len(nodes) <= len(keys)

    def test_remove_old(self):
        not_added_peer = None
        peer_to_remove = None

        while not_added_peer is None:
            k = random_key(self.n_bytes)
            if k == self.key:
                continue
            peer = MockPeer(k)
            peer_to_remove = self.peer_keeper.add_peer(peer)
            if peer_to_remove is not None:
                not_added_peer = peer

        neighs = self.peer_keeper.neighbours(peer_to_remove.key_num ^ 1)
        assert peer_to_remove == neighs[0]
        neighs = self.peer_keeper.neighbours(not_added_peer.key_num ^ 1)
        assert not_added_peer != neighs[0]

        self.peer_keeper.pong_timeout = -1
        self.peer_keeper.sync()

        neighs = self.peer_keeper.neighbours(peer_to_remove.key_num ^ 1)
        assert peer_to_remove != neighs[0]
        neighs = self.peer_keeper.neighbours(not_added_peer.key_num ^ 1)
        assert not_added_peer == neighs[0]

    def test_estimated_network_size_buckets_bigger_than_k(self):
        for _ in range(self.peer_keeper.k):
            self.peer_keeper.buckets[0].peers.append(
                dt_p2p_factory.Node(),
            )
        size = self.peer_keeper.get_estimated_network_size()
        self.assertEqual(size, 0)


class MockPeer:
    def __init__(self, key):
        self.key = encode_hex(key)[2:]
        self.key_num = int(self.key, 16)
        self.address = random.randrange(1, 2 ** 32 - 1)
        self.port = random.randrange(1000, 65535)
        self.node = None
        self.node_name = str(uuid.uuid4())

    def __str__(self):
        return self.key

    def __repr__(self):
        return str(self)
