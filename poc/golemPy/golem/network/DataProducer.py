import logging
import os
import struct

from golem.core.variables import LONG_STANDARD_SIZE, BUFF_SIZE

logger = logging.getLogger(__name__)

class DataProducer:
    def __init__( self, dataToSend, session, buffSize = BUFF_SIZE, extraData = None ):
        self.dataToSend = dataToSend
        self.session = session
        self.data = None
        self.it = 0
        self.numSend = 0
        self.extraData = extraData
        self.buffSize = buffSize
        self.loadData()
        self.register()

    def loadData( self ):
        self.size = len( self.dataToSend )
        logger.info( "Sendig file size:{}".format( self.size ) )
        self.data = struct.pack( "!L", self.size )
        dataLen = len( self.data )
        self.data += self.dataToSend[: self.buffSize ]
        self.it = self.buffSize
        self.size += LONG_STANDARD_SIZE

    def register( self ):
        self.session.conn.transport.registerProducer( self, False )

    def resumeProducing( self ):
        if self.data:
            self.session.conn.transport.write( self.data )
            self.numSend += len( self.data )
            self.__printProgress()

            if self.it < len( self.dataToSend ):
                self.data = self.dataToSend[self.it:self.it + self.buffSize]
                self.it += self.buffSize
            else:
                self.data = None
                self.session.dataSent( self.extraData )
#                self.session.taskServer.taskResultSent( self.subtaskId )
                self.session.conn.transport.unregisterProducer()

    def stopProducing( self ):
        pass

    def __printProgress( self ):
        print "\rSending progress {} %                       ".format( int( 100 * float( self.numSend ) / self.size ) ),