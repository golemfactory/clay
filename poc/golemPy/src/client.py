from p2pserver import P2PServer

import time
import uuid

PING_INTERVAL = 1.0

class Client:
    def __init__(self, port):
        self.listenPort = port
        self.lastPingTime = 0.0
        self.publicKey = uuid.uuid1().get_hex()
        self.pingInterval =  PING_INTERVAL
        self.p2pserver = None

    def startNetwork(self):
        print "Starting network ..."
        self.p2pserver = P2PServer(1, self.listenPort, self.publicKey)

    def connect(self, address, port):
        if self.p2pserver:
            self.p2pserver.connect(address, port)
        else:
            print "Trying to connect when server is not started yet"


