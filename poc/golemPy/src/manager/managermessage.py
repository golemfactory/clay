import sys
sys.path.append( '../')
sys.path.append( '../core')

from message import Message

MANAGER_MSG_BASE = 1000

class MessagePeerStatus( Message ):

    Type = MANAGER_MSG_BASE + 1

    ID_STR      = u"ID"
    DATA_STR    = u"DATA"

    def __init__( self, id = "", data = "", dictRepr = None ):
        Message.__init__(self, MessagePeerStatus.Type)

        self.id = id
        self.data = data

        if dictRepr:
            self.id = dictRepr[ self.ID_STR ]
            self.data = dictRepr[ self.DATA_STR ]

    def dictRepr(self):
        return { self.ID_STR : self.id, self.DATA_STR : self.data } 

    def __str__( self ):
        return "{} {}".format( self.id, self.data )

if __name__ == "__main__":

    m = MessagePeerStatus( "test id", "some test data" )
    sm = m.serialize()
    print sm
    mm = Message.deserializeMessage( sm )
    print mm
