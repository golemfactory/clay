from message import MessagePeerStatus
import pickle

class ManagerSession:

    ##########################
    def __init__( self, conn, server, address, port ):
        self.conn       = conn
        self.server     = server
        self.address    = address
        self.port       = port
        self.uid        = None

    ##########################
    def dropped( self ):
        self.conn.close()
        self.server.managerSession = None
        self.server.managerSessionDisconnected( self.uid )

    ##########################
    def interpret( self, msg ):

        type = msg.getType()

        if type == MessagePeerStatus.Type:
            nss = pickle.loads( msg.data )
            self.uid = nss.getUID()
            self.server.nodeStateSnapshotReceived( nss )
        else:
            print "Wrong message received {}".format( msg )

    ##########################
    def sendClientStateSnapshot( self, snapshot ):

        if self.conn and self.conn.isOpen():
            self.conn.sendMessage( MessagePeerStatus( snapshot.uid, pickle.dumps( snapshot ) ) )