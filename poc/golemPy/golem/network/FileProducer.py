import logging
import os
import struct

from golem.core.variables import BUFF_SIZE

logger = logging.getLogger(__name__)

############################################################################
class FileProducer:
    ###################
    def __init__( self, file_, session, buffSize = BUFF_SIZE ):

        self.file_ = file_
        self.session = session
        self.buffSize = buffSize
        self.openFile()
        self.register()

    ###################
    def openFile( self ):
        self.fh = open( self.file_, 'rb' )
        self.size = os.path.getsize( self.file_ )
        logger.info( "Sendig file size:{}".format( self.size ) )
        self._prepareInitData()

    ###################
    def register( self ):
        self.session.conn.transport.registerProducer( self, False )

    ###################
    def resumeProducing( self ):
        if self.data:
            self.session.conn.transport.write( self.data )
            self._printProgress()
            self._prepareData()
        else:
            self.fh.close()
            self.fh =  None
            self.session.fileSent( self.file_ )
            self.session.conn.transport.unregisterProducer()

    ###################
    def stopProducing( self ):
        pass

    ###################
    def clean(self):
        if self.fh is not None:
            self.fh.close()
            self.fh = None

    close = clean

    ###################
    def _prepareInitData(self):
        self.data = struct.pack( "!L", self.size ) + self.fh.read( self.buffSize )

    ###################
    def _prepareData(self):
        self.data = self.fh.read(self.buffSize)

    ###################
    def _printProgress( self ):
        print "\rSending progress {} %                       ".format( int( 100 * float( self.fh.tell() ) / self.size ) ),

#########################################################
class EncryptFileProducer(FileProducer):
    ###################
    def _prepareInitData(self):
        data = self.session.encrypt(self.fh.read( self.buffSize ))
        self.data = struct.pack( "!L", self.size) + struct.pack("!L", len(data)) + data

    ###################
    def _prepareData(self):
        data = self.fh.read( self.buffSize)
        if data:
            data = self.session.encrypt(data)
            self.data = struct.pack("!L", len(data)) + data
        else:
            self.data = None