from golem.core.hostaddress import getHostAddress, getExternalAddress, getHostAddresses

##########################################################
class Node:
    #############################
    def __init__(self, nodeId=None, key=None, prvAddr=None, prvPort=None, pubAddr=None, pubPort=None, natType=None):
        self.nodeId = nodeId
        self.key = key
        self.prvAddr = prvAddr
        self.prvPort = prvPort
        self.pubAddr = pubAddr
        self.pubPort = pubPort
        self.natType = natType
        self.prvAddresses = []

    #############################
    def collectNetworkInfo(self, seedHost=None, useIp6=False):
        self.prvAddr = getHostAddress(seedHost, useIp6)
        if self.prvPort:
            self.pubAddr, self.pubPort, self.natType = getExternalAddress(self.prvPort)
        else:
            self.pubAddr, _, self.natType = getExternalAddress()
        self.prvAddresses = getHostAddresses(useIp6)

    #############################
    def isSuperNode(self):
        if self.pubAddr is None or self.prvAddr is None:
            return False
        return self.pubAddr == self.prvAddr

