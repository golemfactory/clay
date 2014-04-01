from message import Message
from connectionstate import ConnectionState

class ClientManagerConnState( ConnectionState ):

    ############################
    def __init__( self ):
        ConnectionState.__init__( self )
        self.clientManagerSession = None

    ############################
    def setSession( self, session ):
        self.clientManagerSession = session

    ############################
    def connectionMade( self ):
        self.opened = True

    ############################
    def dataReceived(self, data):
        assert self.opened

        self.db.appendString(data)
        mess = Message.deserialize( self.db )
        if mess is None:
            print "Deserialization message failed"
            self.clientManagerSession.interpret( None )

        if self.clientManagerSession:
            for m in mess:
                self.clientManagerSession.interpret(m)
        else:
            print "manager session for connection is None"
            assert False

    ############################
    def connectionLost(self, reason):
        self.opened = False
        self.clientManagerSession.dropped()
