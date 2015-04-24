import time
import logging

from golem.core.variables import K, CONCURRENCY

logger = logging.getLogger(__name__)

class PeerKeeper:

    #############################
    def __init__(self, peerKeyId, kSize = 512 ):
        self.peerKeyId = peerKeyId
        self.longId = long( peerKeyId, 16 )
        self.k                      = K
        self.concurrency            = CONCURRENCY
        self.kSize = kSize
        self.buckets = [KBucket( 0, 2 ** kSize - 1, self.k )]

    #############################
    def addPeer(self, peerKeyId, peerId, ip, port):
        if peerKeyId == self.peerKeyId:
            logger.warning("Trying to add self to Routing table")
            return
        peerKeyLongId = long( peerKeyId, 16 )

        peerInfo = PeerInfo(peerId, peerKeyLongId, ip, port)
        bucket = self.bucketForNode( peerKeyLongId )
        peerToRemove = bucket.addNode( peerInfo )
        if peerToRemove:
            if bucket.start <= self.longId <= bucket.end:
                self.splitBucket(bucket)
         #       return self.addPeer(peerKeyId, peerId, ip, port)
            return peerToRemove

        for bucket in self.buckets:
            logger.debug( "Bucket {}-{}, nodes {}".format(bucket.start, bucket.end, len( bucket.nodes ) ) )
        return None

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
    def cntDistance(self, peerKeyId):

        return self.longId ^ long( peerKeyId, 16 )

class PeerInfo:
    def __init__(self, nodeId, nodeKeyId, ip, port):
        self.nodeId = nodeId
        self.nodeKeyId = nodeKeyId
        self.ip = ip
        self.port = port

    def __str__(self, nodeId):
        print nodeId

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
        if node.nodeKeyId in self.nodes:
            self.nodes[node.nodeKeyId].remove()
            self.nodes[node.nodeKeyId].append()
        elif len(self.nodes) < self.k:
            self.nodes.append( node )
        else:
            self.replacementNodes.append( node )
            return self.nodes[0]

    def split(self):
        midpoint = (self.start + self.end) / 2
        lower = KBucket(self.start, midpoint, self.k)
        upper = KBucket(midpoint + 1, self.end, self.k)
        for node in self.nodes:
            if node.nodeKeyId <= midpoint:
                lower.addNode( node )
            else:
                upper.addNode( node )
        for node in self.replacementNodes:
            if node.nodeKeyId <= midpoint:
                lower.replacementNodes.append( node )
            else:
                upper.replacementNodes.append( node )
        return lower, upper

    def __str__(self):
        return "start: {}, end: {} nodes {}".format(self.start, self.end, len(self.nodes ))

