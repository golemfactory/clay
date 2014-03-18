import abc
import json
from databuffer import DataBuffer

class Message:

    def __init__( self, type ):
        self.type = type
        self.serializer = DataBuffer()

    def getType( self ):
        return self.type

    def serialize( self ):
        return json.dumps( [ self.type, self.dictRepr() ] )

    def serializeToBuffer( self, db ):
        assert isinstance( db, DataBuffr )
        db.appendLenPrefixedString( self.serialize() )

    @classmethod
    def deserialize( cls, db ):
        assert isinstance( db, DataBuffer )
        messages = []
        msg = db.readLenPrefixedString()

        while msg:
            m = cls.deserializeMessage( msg )
            
            if m is None:
                print "Failed to deserialize message {}".format( msg )
                assert false
 
            messages.append( m )
            msg = db.readLenPrefixedString()

        return messages
  
    @classmethod
    def deserializeMessage( cls, msg ):
        jsonRepr = json.loads( msg )

        msgType = jsonRepr[ 0 ]
        dRepr   = jsonRepr[ 1 ]

        if msgType == MessageHello.Type:
            return MessageHello( dictRepr = dRepr )
        elif msgType == MessagePing.Type:
            return MessagePing( dictRepr = dRepr )
        elif msgType == MessagePong.Type:
            return MessagePong( dictRepr = dRepr )

        return None

    @abc.abstractmethod
    def dictRepr(self):
        """
        Returns dictionary/list representation of 
        any subclassed message
        """
        return

    def __str__( self ):
        return "{}".format( self.__class__ )

    def __repr__( self ):
        return "{}".format( self.__class__ )

