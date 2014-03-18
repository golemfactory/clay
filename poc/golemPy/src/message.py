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