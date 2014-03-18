from twisted.internet.protocol import Protocol 
from message import *

class GolemProtocol(Protocol):

    def __init__(self, client):
        self.client = client

    def sendMessage(self, msg):
        sMessage = msg.serialize()
        print "Sending message {} to {}".format(msg, self.transport.getPeer())
        self.transport.write(sMessage)

    def connectionMade(self):
        print "Connection made"

    def dataReceived(self, data):
        mess = Message.deserialize(data)
        if mess is None:
            print "Deserialization message failed"
            return

        peer = self.transport.getPeer()
        for m in mess:
            print "Received message {} from {}".format(m, peer)
            msg = self.client.interpret(m)
            if msg:
                self.sendMessage(msg)