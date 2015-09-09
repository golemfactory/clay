import random
from copy import copy

class NetworkSimulator:
    def __init__(self):
        self.nodes = {}

    def __str__(self):
        answ = []
        for node, nodeCon in self.nodes.items():
            answ.append("{}: degree{}, conn: {}\n".format(node, len(nodeCon), sorted(nodeCon)))
        return "".join(answ)

    def addNode(self, name=None) :
        if name is None:
            name = self.generateName()

        if name in self.nodes:
            return

        self.nodes[ name ] = set()
        self.connectNode(name)
        return name

    def connectNode(self, node):
        if len (self.nodes) <= 1:
            return

        while True:
            seedNode = random.sample(self.nodes.keys(), 1)[0]
            if seedNode != node:
                break

        self.nodes[ seedNode ].add(node)
        self.nodes[ node ].add(seedNode)

    def sync_network(self, optPeers = 4):
        for node in self.nodes.keys():
            if len (self.nodes[node]) < optPeers:
                newPeers = set()
                for peer in copy(self.nodes[node]):
                    if len(self.nodes[node]) < optPeers:
                        self.nodes[node] |= self.nodes[peer]
                        if node in self.nodes[ node ]:
                            self.nodes[ node ].remove(node)


    def generateName(self):
        num =  len(self.nodes) + 1
        return "node{}".format(str(num).zfill(3))

    def getDegree(self, node_id):
        return len(self.nodes[ node_id ])

    def getAvgNeighboursDegree(self, node_id):
        sD = 0
        if len(self.nodes[ node_id ]) == 0:
            return 0.0
        for n in self.nodes[node_id]:
            sD += len(self.nodes[ n ])
        return float(sD) / len(self.nodes[ node_id ])

    def minDegree(self):
        if len (self.nodes) == 0:
            return 0
        mD = float("inf")
        for nodeCon in self.nodes.itervalues():
            if len(nodeCon) < mD:
                mD = len(nodeCon)

        return mD

    def maxDegree(self):
        mD = 0
        for nodeCon in self.nodes.itervalues():
            if len(nodeCon) > mD:
                mD = len(nodeCon)

        return mD

    def avgDegree(self):
        sD = 0
        for nodeCon in self.nodes.itervalues():
            sD += len(nodeCon)

        return float(sD) / len(self.nodes)

# Preferentail Attachment newtork simulator
class PANetworkSimulator(NetworkSimulator):
    def connectNode(self, node):
        sum_degrees = 0
        for node2Con in self.nodes.values():
            sum_degrees += len(node2Con)

        connected = False
        while not connected:
            for node2, node2Con in self.nodes.items():
                if sum_degrees == 0:
                    p = 1
                else:
                    p = float(len(node2Con)) / float(sum_degrees)
                r = random.random()
                if r < p:
                    self.nodes[ node ].add(node2)
                    self.nodes[ node2 ].add(node)
                    connected = True

