import sys
sys.path.append( '/..')

from connectionstate import ConnectionState

class ManagerConnectionState(ConnectionState):

    def __init__( self ):
        pass

    def dataReceived(self, data):
        assert self.opened

        self.db.appendString(data)
        mess = Message.deserialize(self.db)
        if mess is None:
            print "Deserialization message failed"
            self.peer.interpret(None)

        if self.peer:
            for m in mess:
                self.peer.interpret(m)
        else:
            print "Peer for connection is None"
            assert False
