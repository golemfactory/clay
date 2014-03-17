from twisted.web import server, resource
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol, TCP4ServerEndpoint
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.amp import AMP
from twisted.protocols.basic import LineReceiver
import json
import struct

PingMessage = "\0x02"
PongMessage = "\0x03"

class Message:
    def __init__(self, type):
        self.type = type

    def __str__(self):
        return "{}".format(self.__class__)

    def serialize(self):
        mess = self.serializeTyped()

        s = bytearray()
        s.append(0)
        s.append(0)
        s.append(0)
        s.append(0)

        s += mess

        l = len(s) - 4 

        s[0] = (l >> 24) & 0xff
        s[1] = (l >> 16) & 0xff
        s[2] = (l >> 8) & 0xff
        s[3] = l & 0xff

        return s
       
    @classmethod
    def deserialize(cls, message):

        if(len(message) < 4):
            print "Message shorter than 4 bytes"
            return None

        print message[0].__class__
        l =  message[0] & 0xff << 24
        l += message[1] << 16 & 0xff
        l += message[2] <<  8 & 0xff
        l += message[3] <<  0 & 0xff

        m = message[4:]

        if l != len(m):
            print "Wrong message length: {} != {}".format(l, len(m))
            return None

        dMessage = json.loads(str(m))
        messType = dMessage[0]

        if messType == HelloMessage.Type:
            return HelloMessage()
        elif messType == PingMessage.Type:
            return PingMessage()
        elif messType == PongMessage.Type:
            return PongMessage()
        
        return None
     
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



class GolemProtocol(LineReceiver):

    def __init__(self):
        self.setRawMode()

    def sendMessage(self, msg):
        sMessage = msg.serialize()
        print "Sending: {}".format(msg)
        self.transport.write(sMessage)

    def connectionMade(self):
        print "Connection made"

    def rawDataReceived(self, data):  
        print data.__class__
        print "Received data: {}".format(Message.deserialize(data))

    def lineReceived(self, line):
        self.setRawMode()
        return super(GolemProtocol, self).lineReceived(line)

    #def dataReceived(self, data):
    #    print "Received data: {}".format(Message.deserialize(data))


class Client:

    def __init__(self, port):
        self.listenPort = port

    def start(self):
        print "Start listening ..."
        endpoint = TCP4ServerEndpoint(reactor, self.listenPort)
        endpoint.listen(Factory.forProtocol(GolemProtocol))

    def gotProtocol(self, p):
        p.sendMessage(HelloMessage())

    def connect(self, address, port):
        print "Connecting to host {} : {}".format(address ,port)
        endpoint = TCP4ClientEndpoint(reactor, address, port)
        endpoint.connect(Factory.forProtocol(AMP))
        d = connectProtocol(endpoint, GolemProtocol())
        d.addCallback(self.gotProtocol)
       

if __name__ == "__main__":
    m1 = HelloMessage()
    sm1 = m1.serialize()
    m2 = PingMessage()
    sm2 = m2.serialize()
    m3 = PongMessage()
    sm3 = m3.serialize()

    print Message.deserialize(sm1)
    print Message.deserialize(sm2)
    print Message.deserialize(sm3)

