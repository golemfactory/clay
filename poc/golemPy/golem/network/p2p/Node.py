from golem.core.hostaddress import get_host_address, get_external_address, get_host_addresses

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
    def collectNetworkInfo(self, seed_host=None, use_ipv6=False):
        self.prvAddr = get_host_address(seed_host, use_ipv6)
        if self.prvPort:
            self.pubAddr, self.pubPort, self.natType = get_external_address(self.prvPort)
        else:
            self.pubAddr, _, self.natType = get_external_address()
        self.prvAddresses = get_host_addresses(use_ipv6)

    #############################
    def isSuperNode(self):
        if self.pubAddr is None or self.prvAddr is None:
            return False
        return self.pubAddr == self.prvAddr

