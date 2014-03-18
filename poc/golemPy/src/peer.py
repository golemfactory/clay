#from client import Client
from message import *


class PeerSession:
    StateInitialize = 0
    StateConnecting = 1
    StateConnected  = 2 

    def __init__(self, client, address, port):
        self.client = client
        self.address = address
        self.port = port
        self.state = PeerSession.StateInitialize

    def __str__(self):
        return "{} : {}".format(self.address, self.port)
     
    def start(self):
        self.sendHello()
    
    def disconnect(self):
        pass
    
    def ping(self):
        pass
    
    def setConnecting(self):
        self.state = PeerSession.StateConnecting

    def setConnected(self):
        self.state = PeerSession.StateConnected

    def getState(self):
        return self.state

    # private
       
    def sendHello(self):
        self.send(HelloMessage())

    def send(self, message):
        self.client.sendMessage(self, message)