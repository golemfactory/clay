from twisted.web import server, resource
from twisted.internet import reactor, task
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol, TCP4ServerEndpoint
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.amp import AMP
from twisted.protocols.basic import LineReceiver

import json
import struct
import time

PingMessage = "\0x02"
PongMessage = "\0x03"

class Message:
    def __init__(self, type):
        self.type = type

    def __str__(self):
        return "{}".format(self.__class__)

    def getType(self):
        return self.type

    def serialize(self):
        mess = self.serializeTyped()
        return struct.pack("!L", len(mess)) + mess

    @classmethod
    def deserialize(cls, message):
        curIdx = 0
        
        messages = []
        
        while curIdx < len(message):
            msg, l = cls.deserializeSingle( message[curIdx:] )
            
            if msg is None:
                print "Failed to deserialize multiple at: {} {}".format( curIdx, message[curIdx:] )

            curIdx += l
            messages.append( msg )
            
        return messages
  
    @classmethod
    def deserializeSingle(cls, message):

        if(len(message) < 4):
            print "Message shorter than 4 bytes"
            return None, 0

        (l,) = struct.unpack( "!L", message[0:4])

        m = message[4:l + 4]

        if l > len(m):
            print "Wrong message length: {} > {}".format(l, len(m))
            return None, 0

        dMessage = json.loads(str(m))
        messType = dMessage[0]

        if messType == HelloMessage.Type:
            return HelloMessage(), l + 4
        elif messType == PingMessage.Type:
            return PingMessage(), l + 4
        elif messType == PongMessage.Type:
            return PongMessage(), l + 4
        
        return None, 0
     
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
            msg = self.client.interpret(self, m)
            if msg:
                self.sendMessage(msg)

class GolemServerFactory(Factory):

    def __init__(self, client):
        self.client = client

    def buildProtocol(self, addr):
        return GolemProtocol(self.client)



class Client:

    def __init__(self, port):
        self.listenPort = port
        self.lastPingTime = 0.0
        self.peer = None
        self.t = task.LoopingCall(self.doWork)
        self.t.start(0.5)

    def doWork(self):
        if self.peer and time.time() - self.lastPingTime > 0.5:
            self.peer.sendMessage(PingMessage())

    def start(self):
        print "Start listening ..."
        endpoint = TCP4ServerEndpoint(reactor, self.listenPort)
        endpoint.listen(GolemServerFactory(self))

    def connected(self, p):
        assert isinstance(p, GolemProtocol)
        self.peer = p
        p.sendMessage(HelloMessage())
        p.sendMessage(PingMessage())
        

    def interpret(self, p, mess):

        type = mess.getType()

        if type == PingMessage.Type:
            self.lastPingTime = time.time()
            return PongMessage()
        elif type == PongMessage.Type:
            pass
        elif type == HelloMessage.Type:
            return PingMessage()

        return None

    def connect(self, address, port):
        print "Connecting to host {} : {}".format(address ,port)
        endpoint = TCP4ClientEndpoint(reactor, address, port)
        endpoint.connect(Factory.forProtocol(AMP))
        d = connectProtocol(endpoint, GolemProtocol(self))
        d.addCallback(self.connected)
       

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

    reactor.add()

