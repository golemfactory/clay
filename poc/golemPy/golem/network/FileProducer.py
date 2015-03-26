import logging
import os
import struct

from golem.core.variables import BUFF_SIZE

logger = logging.getLogger(__name__)

class FileProducer:
    def __init__( self, file_, session, buffSize = BUFF_SIZE ):

        self.file_ = file_
        self.session = session
        self.buffSize = buffSize
        self.openFile()
        self.register()

    def openFile( self ):
        self.fh = open( self.file_, 'rb' )
        self.size = os.path.getsize( self.file_ )
        logger.info( "Sendig file size:{}".format( self.size ) )
        self.data = struct.pack( "!L", self.size ) + self.fh.read( self.buffSize )

    def register( self ):
        self.session.conn.transport.registerProducer( self, False )

    def resumeProducing( self ):
        if self.data:
            self.session.conn.transport.write( self.data )
            self.__printProgress()
            self.data = self.fh.read( self.buffSize )
        else:
            self.fh.close()
            self.fh =  None
            self.session.fileSent( self.file_ )
            self.session.conn.transport.unregisterProducer()

    def stopProducing( self ):
        pass

    def clean(self):
        if self.fh is not None:
            self.fh.close()

    def __printProgress( self ):
        print "\rSending progress {} %                       ".format( int( 100 * float( self.fh.tell() ) / self.size ) ),
