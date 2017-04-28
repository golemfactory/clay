import time
import logging
import random
import operator
from collections import deque

logger = logging.getLogger("golem.network.p2p.peerkeeper")

K = 16  # Bucket size
CONCURRENCY = 3  # parallel find node lookup
K_SIZE = 512  # pubkey size
PONG_TIMEOUT = 5   # don't wait for pong longer than this time
REQUEST_TIMEOUT = 10  # find node requests timeout after this time
IDLE_REFRESH = 3  # refresh idle buckets after this time


class PeerKeeper(object):
    """ Keeps information about peers in a network"""
    def __init__(self, key, k_size=K_SIZE):
        """
        Create new peer keeper instance
        :param hex key: hexadecimal representation of a this peer key
        :param int k_size: pubkey size
        """
        self.key = key  # peer's public key
        self.key_num = long(key, 16)  # peer's public key in long format
        self.k = K  # bucket size
        self.concurrency = CONCURRENCY  # parallel find node lookup
        self.k_size = k_size  # pubkey size
        self.buckets = [KBucket(0, 2 ** k_size - 1, self.k)]
        self.pong_timeout = PONG_TIMEOUT
        self.request_timeout = REQUEST_TIMEOUT
        self.idle_refresh = IDLE_REFRESH
        self.sessions_to_end = []  # Node
        self.expected_pongs = {}  # key: key, value: (Node, timestamp)
        self.find_requests = {}  # key: key_num, value: list

    def __str__(self):
        return "\n".join([str(bucket) for bucket in self.buckets])

    def restart(self, key):
        """ Restart peer keeper after peer key has changed. Remove all buckets and empty all queues.
        :param hex key: hexadecimal representation of a peer's public key
        """
        self.key = key
        self.key_num = long(key, 16)
        self.buckets = [KBucket(0, 2 ** self.k_size - 1, self.k)]
        self.expected_pongs = {}
        self.find_requests = {}
        self.sessions_to_end = []

    def add_peer(self, peer_info):
        """ Try to add information about new peer. If it's possible just add it to a proper bucket. Otherwise try
        to find a candidate to replace.
        :param Node peer_info: information about a new peer
        :return None|Node: None if peer has been added to a bucket or if there is no candidate for replacement,
        otherwise return a candidate to replacement.
        """
        if peer_info.key == self.key:
            logger.warning("Trying to add self to Routing table")
            return

        key_num = long(peer_info.key, 16)

        bucket = self.bucket_for_peer(key_num)
        peer_to_remove = bucket.add_peer(peer_info)
        if peer_to_remove:
            if bucket.start <= self.key_num <= bucket.end:
                self.split_bucket(bucket)
                return self.add_peer(peer_info)
            else:
                self.expected_pongs[peer_to_remove.key] = (peer_info, time.time())
                return peer_to_remove

        for bucket in self.buckets:
            logger.debug(str(bucket))
        return None

    def set_last_message_time(self, key):
        """ Set current time as a last message time for a bucket which range contain given key.
        :param hex key: some peer public key in hexadecimal format
        """
        if not key:
            return

        for i, bucket in enumerate(self.buckets):
            if bucket.start <= long(key, 16) < bucket.end:
                self.buckets[i].last_updated = time.time()
                break

    def get_random_known_peer(self):
        """ Return random peer from any bucket
        :return Node|None: information about random peer
        """
        bucket = self.buckets[random.randint(0, len(self.buckets) - 1)]
        if len(bucket.peers) > 0:
            return bucket.peers[random.randint(0, len(bucket.peers) - 1)]
        else:
            return None

    def pong_received(self, key):
        """ React to the fact that pong message was received from peer with given key
        :param hex key: public key of a node that has send pong message
        """
        if key in self.expected_pongs:
            del self.expected_pongs[key]

    def bucket_for_peer(self, key_num):
        """ Find a bucket which contains given num in it's range
        :param long key_num: key long representation for which a bucket should be found
        :return KBucket: bucket containing key in it's range
        """
        for bucket in self.buckets:
            if bucket.start <= key_num < bucket.end:
                return bucket

    def split_bucket(self, bucket):
        """ Split given bucket into two buckets
        :param KBucket bucket: bucket to be split
        """
        logger.debug("Splitting bucket")
        buck1, buck2 = bucket.split()
        idx = self.buckets.index(bucket)
        self.buckets[idx] = buck1
        self.buckets.insert(idx + 1, buck2)

    def cnt_distance(self, key):
        """ Return distance between this peer and peer with a given key. Distance is a xor between keys.
        :param hex key: other peer public key
        :return long: distance to other peer
        """
        return self.key_num ^ long(key, 16)

    def sync(self):
        """ Sync peer keeper state. Remove old requests and expected pongs, add new peers if old peers didn't answer
         to ping. Additionally prepare a list of peers that should be found to correctly fill the buckets.
        :return dict: information about peers that should be found (key and list of closest known neighbours)
        """
        self.__remove_old_expected_pongs()
        self.__remove_old_requests()
        peers_to_find = self.__send_new_requests()
        return peers_to_find

    def neighbours(self, key_num, alpha=None):
        """ Return alpha nearest known neighbours to a peer with given key
        :param long key_num: given key in a long format
        :param None|int alpha: *Default: None* number of neighbours to find. If alpha is set to None then
        default concurrency parameter will be used
        :return list: list of nearest known neighbours
        """
        if not alpha:
            alpha = self.concurrency

        neigh = []
        for bucket in self.buckets_by_id_distance(key_num):
            for peer in bucket.peers_by_id_distance(key_num):
                if long(peer.key, 16) != key_num:
                    neigh.append(peer)
                    if len(neigh) == alpha * 2:
                        break
        return sorted(neigh, key=lambda p: node_id_distance(p, key_num))[:alpha]

    def buckets_by_id_distance(self, key_num):
        """
        Return list of buckets sorted by distance from given key. Bucket middle range element
        will be taken into account
        :param long key_num: given key in long format
        :return list: sorted buckets list
        """
        return sorted(self.buckets, key=operator.methodcaller('id_distance', key_num))

    def __remove_old_expected_pongs(self):
        cur_time = time.time()
        for key, (replacement, time_) in self.expected_pongs.items():
            key_num = long(key, 16)
            if cur_time - time_ > self.pong_timeout:
                peer_info = self.bucket_for_peer(key_num).remove_peer(key_num)
                if peer_info:
                    self.sessions_to_end.append(peer_info)
                if replacement:
                    self.add_peer(replacement)

                del self.expected_pongs[key]

    def __send_new_requests(self):
        peers_to_find = {}
        cur_time = time.time()
        for bucket in self.buckets:
            if cur_time - bucket.last_updated > self.idle_refresh:
                key_num = random.randint(bucket.start, bucket.end)
                self.find_requests[key_num] = cur_time
                peers_to_find[key_num] = self.neighbours(key_num)
                bucket.last_updated = cur_time
        return peers_to_find

    def __remove_old_requests(self):
        cur_time = time.time()
        for key_num, time_ in self.find_requests.items():
            if cur_time - time.time() > self.request_timeout:
                del self.find_requests[key_num]


def node_id_distance(node_info, key_num):
    """ Return distance in XOR metrics between two peers when we have full information about one node and only public
     key of a second node
    :param Node node_info: information about node (peer)
    :param long key_num: other node public key in long format
    :return long: distance between two peers
    """
    return long(node_info.key, 16) ^ key_num


class KBucket(object):
    """ K-bucket for keeping information about peers from a given distance range """
    def __init__(self, start, end, k):
        """ Create new bucket with range [start, end)
        :param long start: bucket range start
        :param long end: bucket range end
        :param int k: bucket size
        """
        self.start = start
        self.end = end
        self.k = k
        self.peers = deque()
        self.last_updated = time.time()

    def add_peer(self, peer):
        """ Try to append peer to a bucket. If it's already in a bucket remove it and append it at the end.
        If a bucket is full then return oldest peer in a bucket as a candidate for replacement
        :param Node peer: peer to add
        :return Node|None: oldest peer in a bucket, if a new peer hasn't been added or None otherwise
        """
        logger.debug("KBucket adding peer {}".format(peer))
        self.last_updated = time.time()
        old_peer = None
        for p in self.peers:
            if p.key == peer.key:
                old_peer = p
                break
        if old_peer:
            self.peers.remove(old_peer)
            self.peers.append(peer)
        elif len(self.peers) < self.k:
            self.peers.append(peer)
        else:
            return self.peers[0]
        return None

    def remove_peer(self, key_num):
        """ Remove peer with given key from this bucket
        :param long key_num: public key of a node that should be removed from this bucket in long format
        :return Node|None: information about peer if it was in this bucket, None otherwise
        """
        for peer in self.peers:
            if long(peer.key, 16) == key_num:
                self.peers.remove(peer)
                return peer
        return None

    def id_distance(self, key_num):
        """ Return distance from a middle of a bucket range to a given key
        :param long key_num:  other node public key in long format
        :return long: distance from a middle of this bucket to a given key
        """
        return ((self.start + self.end) / 2) ^ key_num

    def peers_by_id_distance(self, key_num):
        return sorted(self.peers, key=lambda p: node_id_distance(p, key_num))

    def split(self):
        """ Split bucket into two buckets
        :return (KBucket, KBucket): two buckets that were created from this bucket
        """
        midpoint = (self.start + self.end) / 2
        lower = KBucket(self.start, midpoint, self.k)
        upper = KBucket(midpoint + 1, self.end, self.k)
        for peer in self.peers:
            if long(peer.key, 16) < midpoint:
                lower.add_peer(peer)
            else:
                upper.add_peer(peer)
        return lower, upper

    def __str__(self):
        return "Bucket: {} - {} peers {}".format(self.start, self.end, len(self.peers))

    @staticmethod
    def __num_to_pow(num):
        pow_ = 512
        while 2 ** pow_ - 1 > num:
            pow_ -= 1
        return pow_
