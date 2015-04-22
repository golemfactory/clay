import time

from golem.core.variables import K, CONCURRENCY

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
            return
        peerKeyId = long( peerKeyId, 16 )

        peerInfo = PeerInfo(peerId, peerKeyId, ip, port)
        bucket = self.bucketForNode( peerKeyId )
        bucket.addNode( peerInfo )

        for bucket in self.buckets:
            print "Bucket {}-{}, nodes {}".format(bucket.start, bucket.end, len( bucket.nodes ) )

    #############################
    def bucketForNode(self, peerKeyId ):
        for bucket in self.buckets:
            if bucket.start <= peerKeyId < bucket.end:
                return bucket





    #############################
    def cntDistance(self, peerKeyId):
        return self.longId ^ long( peerKeyId, 16 )

class PeerInfo:
    def __init__(self, nodeId, nodeKeyId, ip, port):
        self.nodeId = nodeId
        self.nodeKeyId = nodeKeyId
        self.ip = ip
        self.port = port

class KBucket:
    def __init__( self, start, end,  k ):
        print "KBUCKET"
        self.start = start
        self.end = end
        self.k = k
        self.nodes = []
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

