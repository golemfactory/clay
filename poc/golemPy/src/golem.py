from twisted.web import server, resource
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol, TCP4ServerEndpoint
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.amp import AMP
import json

PingMessage = "\0x02"
PongMessage = "\0x03"

class Message:
    def __init__(self, type):
        self.type = type

    def serialize(self):
        mess = self.serializeTyped()

        l = len(mess) 
        s = bytearray()
        s.append((l >> 24) & 0xff)
        s.append((l >> 16) & 0xff)
        s.append((l >> 8) & 0xff)
        s.append(l & 0xff)

        return s + mess;
        
    def serializeTyped(self):
        pass

class HelloMessage(Message):
    Type = 0
    def __init__(self):
        Message.__init__(self, HelloMessage.Type)

    def serializeTyped(self):
        return json.dumps([HelloMessage.Type, "Hello World !!!"])

class PingMessage(Message):
    Type = 1
    def __init__(self):
        Message.__init__(self, PingMessage.Type)

    def serializeTyped(self):
        return json.dumps([PingMessage.Type, "Ping"])

class PongMessage(Message):
    Type = 2
    def __init__(self):
        Message.__init__(self, PongMessage.Type)

    def serializeTyped(self):
        return json.dumps([PongMessage.Type ,"Pong"])



class GolemProtocol(Protocol):
    def sendMessage(self, msg):
        buf = self.seal(len(msg))
        out = buf + msg
        print self.transport.__repr__()
        print self.transport.__str__()
        self.transport.write(str(out))

    def connectionMade(self):
        print self.transport.__str__()
        print "Connection made"

    def dataReceived(self, data):
        print data


class Client:

    def __init__(self, port):
        self.listenPort = port

    def start(self):
        print "Start listening ..."
        endpoint = TCP4ServerEndpoint(reactor, self.listenPort)
        endpoint.listen(Factory.forProtocol(GolemProtocol))

    def gotProtocol(self, p):
        p.sendMessage("Nie lubie ruskich")

    def connect(self, address, port):
        print "Connecting to host {} : {}".format(address ,port)
        endpoint = TCP4ClientEndpoint(reactor, address, port)
        endpoint.connect(Factory.forProtocol(AMP))
        d = connectProtocol(endpoint, GolemProtocol())
        d.addCallback(self.gotProtocol)
       

if __name__ == "__main__":
    m1 = HelloMessage()
    print m1.serialize()
    m2 = PingMessage()
    print m2.serialize()
    m3 = PongMessage()
    print m3.serialize()