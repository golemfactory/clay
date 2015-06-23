from golem.core.hostaddress import getHostAddress, getExternalAddress

##########################################################
class Node:
    #############################
    def __init__(self, nodeId=None, key=None, prvAddr=None, prvPort=None, pubAddr=None, pubPort=None):
        self.nodeId = nodeId
        self.key = key
        self.prvAddr = prvAddr
        self.prvPort = prvPort
        self.pubAddr = pubAddr
        self.pubPort = pubPort

    #############################
    def collectNetworkInfo(self, seedHost=None):
        self.prvAddr = getHostAddress(seedHost)
        if self.prvPort:
            self.pubAddr, self.pubPort = getExternalAddress(self.prvPort)
        else:
            self.pubAddr, _ = getExternalAddress()

    #############################
    def isSuperNode(self):
        if self.pubAddr is None or self.prvAddr is None:
            return False
        return self.pubAddr == self.prvAddr

