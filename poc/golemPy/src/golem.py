from twisted.web import server, resource
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.amp import AMP

class GolemProtocol(Protocol):
    def seal(self, messSize):
        s = []
        s.append(0x22)
        s.append(0x40)
        s.append(0x08)
        s.append(0x91)
        len = messSize;
        s.append((len >> 24) & 0xff)
        s.append((len >> 16) & 0xff)
        s.append((len >> 8) & 0xff)
        s.append(len & 0xff)
        return s

    def sendMessage(self, msg):
        buf = self.seal(len(msg))
        self.transport.write(buf + msg)

def gotProtocol(p):
    print "gotProtocol"
    p.sendMessage("test Message")

class Client:
    seeds = []

    def connect(self, address, port):
        endpoint = TCP4ClientEndpoint(reactor, address, port)
        endpoint.connect(Factory.forProtocol(AMP))
        d = connectProtocol(endpoint, GolemProtocol())
        d.addCallback(gotProtocol)
       

