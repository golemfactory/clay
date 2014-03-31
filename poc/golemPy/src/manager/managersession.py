from message import MessagePeerStatus
import pickle

class ManagerSession:

    ##########################
    def __init__( self, conn, server, address, port ):
        self.conn       = conn
        self.server     = server
        self.address    = address
        self.port       = port

    ##########################
    def dropped( self ):
        self.conn.close()
        del self.server.managerSession

    ##########################
    def interpret( self, msg ):

        type = msg.getType()

        if type == MessagePeerStatus.Type:
            self.server.nodeStateSnapshotReceived( msg.data )
        else:
            print "Wrong message received {}".format( msg )

    ##########################
    def sendClientStateSnapshot( self, snapshot ):

        if self.conn and self.conn.isOpen():
            self.conn.sendMessage( MessagePeerStatus( snapshot.uid, pickle.dumps( snapshot ) ) )