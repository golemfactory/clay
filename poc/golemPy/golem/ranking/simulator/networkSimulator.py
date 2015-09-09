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

    def add_node(self, name=None) :
        if name is None:
            name = self.generate_name()

        if name in self.nodes:
            return

        self.nodes[ name ] = set()
        self.connect_node(name)
        return name

    def connect_node(self, node):
        if len (self.nodes) <= 1:
            return

        while True:
            seed_node = random.sample(self.nodes.keys(), 1)[0]
            if seed_node != node:
                break

        self.nodes[ seed_node ].add(node)
        self.nodes[ node ].add(seed_node)

    def sync_network(self, opt_peers = 4):
        for node in self.nodes.keys():
            if len (self.nodes[node]) < opt_peers:
                new_peers = set()
                for peer in copy(self.nodes[node]):
                    if len(self.nodes[node]) < opt_peers:
                        self.nodes[node] |= self.nodes[peer]
                        if node in self.nodes[ node ]:
                            self.nodes[ node ].remove(node)


    def generate_name(self):
        num =  len(self.nodes) + 1
        return "node{}".format(str(num).zfill(3))

    def get_degree(self, node_id):
        return len(self.nodes[ node_id ])

    def get_avg_neighbours_degree(self, node_id):
        sd = 0
        if len(self.nodes[ node_id ]) == 0:
            return 0.0
        for n in self.nodes[node_id]:
            sd += len(self.nodes[ n ])
        return float(sd) / len(self.nodes[ node_id ])

    def min_degree(self):
        if len (self.nodes) == 0:
            return 0
        md = float("inf")
        for nodeCon in self.nodes.itervalues():
            if len(nodeCon) < md:
                md = len(nodeCon)

        return md

    def max_degree(self):
        md = 0
        for nodeCon in self.nodes.itervalues():
            if len(nodeCon) > md:
                md = len(nodeCon)

        return md

    def avg_degree(self):
        sd = 0
        for nodeCon in self.nodes.itervalues():
            sd += len(nodeCon)

        return float(sd) / len(self.nodes)

# Preferentail Attachment newtork simulator
class PANetworkSimulator(NetworkSimulator):
    def connect_node(self, node):
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

