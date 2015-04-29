import time
import logging

from golem.core.variables import K, CONCURRENCY

logger = logging.getLogger(__name__)

class PeerKeeper:

    #############################
    def __init__(self, peerKey, kSize = 512 ):
        self.peerKey = peerKey
        self.peerKeyId = long( peerKey, 16 )
        self.k                      = K
        self.concurrency            = CONCURRENCY
        self.kSize = kSize
        self.buckets = [KBucket( 0, 2 ** kSize - 1, self.k )]
        self.expectedPongs = {}
        self.pongTimeout = 5

    #############################
    def addPeer(self, peerKey, peerId, ip, port):
        if peerKey == self.peerKey:
            logger.warning("Trying to add self to Routing table")
            return
        peerKeyId = long( peerKey, 16 )

        peerInfo = PeerInfo(peerId, peerKey, ip, port)
        bucket = self.bucketForNode( peerKeyId )
        peerToRemove = bucket.addNode( peerInfo )
        if peerToRemove:
            if bucket.start <= self.peerKeyId <= bucket.end:
                self.splitBucket(bucket)
                return self.addPeer(peerKey, peerId, ip, port)
            else:
                self.expectedPongs[peerToRemove.nodeKeyId] = (peerInfo, time.time() )
                return peerToRemove


        for bucket in self.buckets:
            logger.debug( "Bucket 2^{}-2^{}, nodes {}".format(self.__numToPow(bucket.start), self.__numToPow(bucket.end), len( bucket.nodes ) ) )
        return None

    #############################
    def pongReceived(self, peerKey, peerId, ip, port ):
        peerKeyId = long( peerKey, 16 )
        if peerKeyId in self.expectedPongs:
            del self.expectedPongs[peerKeyId]


    #############################
    def bucketForNode(self, peerKeyId ):
        for bucket in self.buckets:
            if bucket.start <= peerKeyId < bucket.end:
                return bucket

    #############################
    def splitBucket(self, bucket):
        buck1, buck2 = bucket.split()
        idx = self.buckets.index(bucket)
        self.buckets[idx] = buck1
        self.buckets.insert(idx + 1, buck2)


    #############################
    def cntDistance(self, peerKey):

        return self.peerKeyId ^ long( peerKey, 16 )

    #############################
    def syncNetwork(self):
        for peerKeyId, (replacement, time_) in self.expectedPongs.items():
            current_time = time.time()
            if current_time - time_ > self.pongTimeout:
                self.bucketForNode( peerKeyId ).removeNode( peerKeyId )
                if replacement:
                    self.addPeer( replacement.nodeKey, replacement.nodeId,  replacement.ip, replacement.port )
                del self.expectedPongs[peerKeyId]


    #############################
    def __numToPow(self, num):
        pow = self.kSize
        while 2 ** pow - 1 > num:
            pow -= 1
        return pow



class PeerInfo:
    def __init__(self, nodeId, nodeKey, ip, port):
        self.nodeId = nodeId
        self.nodeKey = nodeKey
        self.nodeKeyId = long( nodeKey, 16 )
        self.ip = ip
        self.port = port

    def __str__(self ):
        return self.nodeId

from collections import deque

class KBucket:
    def __init__( self, start, end,  k ):
        self.start = start
        self.end = end
        self.k = k
        self.nodes = deque()
        self.replacementNodes = []
        self.lastUpdated = time.time()

    def addNode( self, node ):
        logger.debug("KBucekt adding node {}".format( node ) )
        if node in self.nodes:
            self.nodes.remove(node )
            self.nodes.append(node )
        elif len(self.nodes) < self.k:
            self.nodes.append( node )
        else:
            self.replacementNodes.append( node )
            return self.nodes[0]
        return None

    def removeNode( self, nodeKeyId ):
        print self.nodes
        for node in self.nodes:
            if node.nodeKeyId == nodeKeyId:
                self.nodes.remove(node)
                return


    def split(self):
        midpoint = (self.start + self.end) / 2
        lower = KBucket(self.start, midpoint, self.k)
        upper = KBucket(midpoint + 1, self.end, self.k)
        for node in self.nodes:
            if node.nodeKeyId < midpoint:
                lower.addNode( node )
            else:
                upper.addNode( node )
        for node in self.replacementNodes:
            if node.nodeKeyId < midpoint:
                lower.replacementNodes.append( node )
            else:
                upper.replacementNodes.append( node )
        return lower, upper

    def __str__(self):
        return "start: {}, end: {} nodes {}".format(self.start, self.end, len(self.nodes ))

