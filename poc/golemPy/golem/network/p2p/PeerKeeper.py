import time
import logging
import random
import operator

from golem.core.variables import K, CONCURRENCY

logger = logging.getLogger(__name__)

class PeerKeeper:

    #############################
    def __init__(self, peer_key, k_size = 512):

        self.peer_key = peer_key
        self.peer_key_id = long(peer_key, 16)
        self.k                      = K
        self.concurrency            = CONCURRENCY
        self.k_size = k_size
        self.buckets = [KBucket(0, 2 ** k_size - 1, self.k)]
        self.expected_pongs = {}
        self.find_requests = {}
        self.pong_timeout = 5
        self.request_timeout = 10
        self.idle_refresh = 3
        self.sessions_to_end = []

    #############################
    def __str__(self):
        return "\n".join([ str(bucket) for bucket in self.buckets ])

    #############################
    def add_peer(self, peer_key, peer_id, ip, port, node_info):
        if peer_key == self.peer_key:
            logger.warning("Trying to add self to Routing table")
            return

        if not peer_key:
            return

        peer_key_id = long(peer_key, 16)

        peer_info = PeerInfo(peer_id, peer_key, ip, port, node_info)
        bucket = self.bucket_for_node(peer_key_id)
        peer_to_remove = bucket.add_node(peer_info)
        if peer_to_remove:
            if bucket.start <= self.peer_key_id <= bucket.end:
                self.split_bucket(bucket)
                return self.add_peer(peer_key, peer_id, ip, port, node_info)
            else:
                self.expected_pongs[peer_to_remove.node_key_id] = (peer_info, time.time())
                return peer_to_remove


        for bucket in self.buckets:
            logger.debug(str(bucket))
        return None

    #############################
    def set_last_message_time(self, peer_key):
        if not peer_key:
            return

        for i, bucket in enumerate(self.buckets):
            if bucket.start <= long(peer_key, 16) < bucket.end:
                self.buckets[i].last_updated = time.time()
                break

    #############################
    def get_random_known_node(self):

        bucket = self.buckets[random.randint(0, len(self.buckets) - 1)]
        if len(bucket.nodes) > 0:
            return bucket.nodes[random.randint(0, len(bucket.nodes) - 1)]

    #############################
    def pong_received(self, peer_key, peer_id, ip, port):
        if not peer_key:
            return
        peer_key_id = long(peer_key, 16)
        if peer_key_id in self.expected_pongs:
            self.sessions_to_end.append(peer_id)
            del self.expected_pongs[peer_key_id]


    #############################
    def bucket_for_node(self, peer_key_id):
        for bucket in self.buckets:
            if bucket.start <= peer_key_id < bucket.end:
                return bucket

    #############################
    def split_bucket(self, bucket):
        logger.debug("Splitting bucket")
        buck1, buck2 = bucket.split()
        idx = self.buckets.index(bucket)
        self.buckets[idx] = buck1
        self.buckets.insert(idx + 1, buck2)


    #############################
    def cnt_distance(self, peer_key):

        return self.peer_key_id ^ long(peer_key, 16)

    #############################
    def sync_network(self):
        self.__remove_old_expected_pongs()
        self.__remove_old_requests()
        nodes_to_find = self.__send_new_requests()
        return nodes_to_find

    #############################
    def __remove_old_expected_pongs(self):
        cur_time = time.time()
        for peer_key_id, (replacement, time_) in self.expected_pongs.items():
            if cur_time - time_ > self.pong_timeout:
                peer_id = self.bucket_for_node(peer_key_id).remove_node(peer_key_id)
                if peer_id:
                    self.sessions_to_end.append(peer_id)
                if replacement:
                    self.add_peer(replacement.node_key, replacement.node_id,  replacement.ip, replacement.port,
                                 replacement.node_info)

                del self.expected_pongs[peer_key_id]

    #############################
    def __send_new_requests(self):
        nodes_to_find = {}
        cur_time = time.time()
        for bucket in self.buckets:
            if cur_time - bucket.last_updated > self.idle_refresh:
                node_key_id = random.randint(bucket.start, bucket.end)
                self.find_requests[node_key_id] = cur_time
                nodes_to_find[node_key_id] = self.neighbours(node_key_id)
                bucket.last_updated = cur_time
        return nodes_to_find

    #############################
    def neighbours(self, node_key_id, alpha = None):
        if not alpha:
            alpha = self.concurrency

        neigh = []
        for bucket in self.buckets_by_id_distance(node_key_id):
            for node in bucket.nodes_by_id_distance(node_key_id):
                if node.node_key_id != node_key_id:
                    neigh.append(node)
                    if len(neigh) == alpha * 2:
                        break
        return sorted(neigh, key = operator.methodcaller('id_distance', node_key_id))[:alpha]

    #############################
    def buckets_by_id_distance(self, node_key_id):
        return sorted(self.buckets, key=operator.methodcaller('id_distance', node_key_id))

    #############################
    def __remove_old_requests(self):
        cur_time = time.time()
        for peer_key_id, time_ in self.find_requests.items():
            if cur_time - time.time() > self.request_timeout:
                del self.find_requests[peer_key_id]

##########################################################

class PeerInfo:
    #############################
    def __init__(self, node_id, node_key, ip, port, node_info):
        self.node_id = node_id
        self.node_key = node_key
        self.node_key_id = long(node_key, 16)
        self.ip = ip
        self.port = port
        self.node_info = node_info

    #############################
    def id_distance(self, node_key_id):
        return self.node_key_id ^ node_key_id

    #############################
    def __str__(self):
        return self.node_id

##########################################################

from collections import deque

class KBucket:
    #############################
    def __init__(self, start, end,  k):
        self.start = start
        self.end = end
        self.k = k
        self.nodes = deque()
        self.last_updated = time.time()

    #############################
    def add_node(self, node):
        logger.debug("KBucekt adding node {}".format(node))
        self.last_updated = time.time()
        if node in self.nodes:
            self.nodes.remove(node)
            self.nodes.append(node)
        elif len(self.nodes) < self.k:
            self.nodes.append(node)
        else:
            return self.nodes[0]
        return None

    #############################
    def remove_node(self, node_key_id):
        for node in self.nodes:
            if node.node_key_id == node_key_id:
                node_id = node.node_id
                self.nodes.remove(node)
                return node_id
        return None

    #############################
    def id_distance(self, node_key_id):
        return ((self.start + self.end) / 2) ^ node_key_id

    #############################
    def nodes_by_id_distance(self, node_key_id):
        return sorted(self.nodes, key = operator.methodcaller('id_distance', node_key_id))

    #############################
    def split(self):
        midpoint = (self.start + self.end) / 2
        lower = KBucket(self.start, midpoint, self.k)
        upper = KBucket(midpoint + 1, self.end, self.k)
        for node in self.nodes:
            if node.node_key_id < midpoint:
                lower.add_node(node)
            else:
                upper.add_node(node)
        return lower, upper

    #############################
    def __str__(self):
        return "Bucket: {} - {} nodes {}".format(self.start, self.end, len(self.nodes))

    #############################
    def __num_to_pow(self, num):
        pow = 512
        while 2 ** pow - 1 > num:
            pow -= 1
        return pow
