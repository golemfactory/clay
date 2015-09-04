import time
import logging
import random
import operator

from golem.core.variables import K, CONCURRENCY

logger = logging.getLogger(__name__)

class PeerKeeper:

    #############################
    def __init__(self, peerKey, kSize = 512):

        self.peerKey = peerKey
        self.peer_key_id = long(peerKey, 16)
        self.k                      = K
        self.concurrency            = CONCURRENCY
        self.kSize = kSize
        self.buckets = [KBucket(0, 2 ** kSize - 1, self.k)]
        self.expectedPongs = {}
        self.findRequests = {}
        self.pongTimeout = 5
        self.requestTimeout = 10
        self.idleRefresh = 3
        self.sessionsToEnd = []

    #############################
    def __str__(self):
        return "\n".join([ str(bucket) for bucket in self.buckets ])

    #############################
    def add_peer(self, peerKey, peerId, ip, port, node_info):
        if peerKey == self.peerKey:
            logger.warning("Trying to add self to Routing table")
            return

        if not peerKey:
            return

        peer_key_id = long(peerKey, 16)

        peer_info = PeerInfo(peerId, peerKey, ip, port, node_info)
        bucket = self.bucketForNode(peer_key_id)
        peerToRemove = bucket.addNode(peer_info)
        if peerToRemove:
            if bucket.start <= self.peer_key_id <= bucket.end:
                self.splitBucket(bucket)
                return self.add_peer(peerKey, peerId, ip, port, node_info)
            else:
                self.expectedPongs[peerToRemove.nodeKeyId] = (peer_info, time.time())
                return peerToRemove


        for bucket in self.buckets:
            logger.debug(str(bucket))
        return None

    #############################
    def setLastMessageTime(self, peerKey):
        if not peerKey:
            return

        for i, bucket in enumerate(self.buckets):
            if bucket.start <= long(peerKey, 16) < bucket.end:
                self.buckets[i].lastUpdated = time.time()
                break

    #############################
    def getRandomKnownNode(self):

        bucket = self.buckets[random.randint(0, len(self.buckets) - 1)]
        if len(bucket.nodes) > 0:
            return bucket.nodes[random.randint(0, len(bucket.nodes) - 1)]

    #############################
    def pong_received(self, peerKey, peerId, ip, port):
        if not peerKey:
            return
        peer_key_id = long(peerKey, 16)
        if peer_key_id in self.expectedPongs:
            self.sessionsToEnd.append(peerId)
            del self.expectedPongs[peer_key_id]


    #############################
    def bucketForNode(self, peer_key_id):
        for bucket in self.buckets:
            if bucket.start <= peer_key_id < bucket.end:
                return bucket

    #############################
    def splitBucket(self, bucket):
        logger.debug("Splitting bucket")
        buck1, buck2 = bucket.split()
        idx = self.buckets.index(bucket)
        self.buckets[idx] = buck1
        self.buckets.insert(idx + 1, buck2)


    #############################
    def cntDistance(self, peerKey):

        return self.peer_key_id ^ long(peerKey, 16)

    #############################
    def sync_network(self):
        self.__removeOldExpectedPongs()
        self.__removeOldRequests()
        nodesToFind = self.__sendNewRequests()
        return nodesToFind

    #############################
    def __removeOldExpectedPongs(self):
        currentTime = time.time()
        for peer_key_id, (replacement, time_) in self.expectedPongs.items():
            if currentTime - time_ > self.pongTimeout:
                peerId = self.bucketForNode(peer_key_id).removeNode(peer_key_id)
                if peerId:
                    self.sessionsToEnd.append(peerId)
                if replacement:
                    self.add_peer(replacement.nodeKey, replacement.nodeId,  replacement.ip, replacement.port,
                                 replacement.node_info)

                del self.expectedPongs[peer_key_id]

    #############################
    def __sendNewRequests(self):
        nodesToFind = {}
        currentTime = time.time()
        for bucket in self.buckets:
            if currentTime - bucket.lastUpdated > self.idleRefresh:
                nodeKeyId = random.randint(bucket.start, bucket.end)
                self.findRequests[nodeKeyId] = currentTime
                nodesToFind[nodeKeyId] = self.neighbours(nodeKeyId)
                bucket.lastUpdated = currentTime
        return nodesToFind

    #############################
    def neighbours(self, nodeKeyId, alpha = None):
        if not alpha:
            alpha = self.concurrency

        neigh = []
        for bucket in self.bucketsByIdDistance(nodeKeyId):
            for node in bucket.nodesByIdDistance(nodeKeyId):
                if node.nodeKeyId != nodeKeyId:
                    neigh.append(node)
                    if len(neigh) == alpha * 2:
                        break
        return sorted(neigh, key = operator.methodcaller('idDistance', nodeKeyId))[:alpha]

    #############################
    def bucketsByIdDistance(self, nodeKeyId):
        return sorted(self.buckets, key=operator.methodcaller('idDistance', nodeKeyId))

    #############################
    def __removeOldRequests(self):
        currentTime = time.time()
        for peer_key_id, time_ in self.findRequests.items():
            if currentTime - time.time() > self.requestTimeout:
                del self.findRequests[peer_key_id]

##########################################################

class PeerInfo:
    #############################
    def __init__(self, nodeId, nodeKey, ip, port, node_info):
        self.nodeId = nodeId
        self.nodeKey = nodeKey
        self.nodeKeyId = long(nodeKey, 16)
        self.ip = ip
        self.port = port
        self.node_info = node_info

    #############################
    def idDistance(self, nodeKeyId):
        return self.nodeKeyId ^ nodeKeyId

    #############################
    def __str__(self):
        return self.nodeId

##########################################################

from collections import deque

class KBucket:
    #############################
    def __init__(self, start, end,  k):
        self.start = start
        self.end = end
        self.k = k
        self.nodes = deque()
        self.lastUpdated = time.time()

    #############################
    def addNode(self, node):
        logger.debug("KBucekt adding node {}".format(node))
        self.lastUpdated = time.time()
        if node in self.nodes:
            self.nodes.remove(node)
            self.nodes.append(node)
        elif len(self.nodes) < self.k:
            self.nodes.append(node)
        else:
            return self.nodes[0]
        return None

    #############################
    def removeNode(self, nodeKeyId):
        for node in self.nodes:
            if node.nodeKeyId == nodeKeyId:
                nodeId = node.nodeId
                self.nodes.remove(node)
                return nodeId
        return None

    #############################
    def idDistance(self, nodeKeyId):
        return ((self.start + self.end) / 2) ^ nodeKeyId

    #############################
    def nodesByIdDistance(self, nodeKeyId):
        return sorted(self.nodes, key = operator.methodcaller('idDistance', nodeKeyId))

    #############################
    def split(self):
        midpoint = (self.start + self.end) / 2
        lower = KBucket(self.start, midpoint, self.k)
        upper = KBucket(midpoint + 1, self.end, self.k)
        for node in self.nodes:
            if node.nodeKeyId < midpoint:
                lower.addNode(node)
            else:
                upper.addNode(node)
        return lower, upper

    #############################
    def __str__(self):
        return "Bucket: {} - {} nodes {}".format(self.start, self.end, len(self.nodes))

    #############################
    def __numToPow(self, num):
        pow = 512
        while 2 ** pow - 1 > num:
            pow -= 1
        return pow
