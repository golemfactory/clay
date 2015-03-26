import struct
import os
import logging

from golem.core.variables import LONG_STANDARD_SIZE

logger = logging.getLogger(__name__)

class MultiFileConsumer:
    ###################
    def __init__( self, fileList, outputDir, session, extraData ):
        self.fileList = fileList
        self.finalFileList = [ os.path.normpath( os.path.join( outputDir, f ) ) for f in fileList]
        self.fh = None
        self.fileSize = -1
        self.recvSize = 0

        self.outputDir = outputDir

        self.session = session
        self.extraData = extraData

        self.lastPercent = 0
        self.lastData = ''

    ###################
    def dataReceived( self, data ):
        locData = data
        if self.fileSize == -1:
            locData = self.__getFirstChunk( self.lastData + data )

        assert self.fh

        self.recvSize += len( locData )
        if self.recvSize <= self.fileSize:
            self.fh.write( locData )
            self.lastData = ''
        else:
            lastData = len( locData ) - (self.recvSize - self.fileSize)
            print "lastData {}".format( lastData )
            self.fh.write( locData[:lastData] )
            self.lastData = locData[lastData:]

        self.__printProgress()

        if self.recvSize >= self.fileSize:
            self.__endReceivingFile()

    def close(self):
        if self.fh is not None:
            self.fh.close()
            self.fh = None
            if self.recvSize < self.fileSize and len( self.fileList ) > 0:
                os.remove( self.fileList[-1])

    ###################
    def __getFirstChunk( self, data ):
        self.lastPercent = 0
        ( self.fileSize, ) = struct.unpack("!L", data[ :LONG_STANDARD_SIZE ] )
        logger.info( "Receiving file {}, size {}".format( self.fileList[-1], self.fileSize ) )
        assert self.fh is None

        self.fh = open( os.path.join( self.outputDir, self.fileList[-1] ), 'wb' )
        return  data[ LONG_STANDARD_SIZE: ]

    ###################
    def __printProgress( self ):
        prct = int( 100 * self.recvSize / float( self.fileSize ) )
        if prct > 100:
            prct = 100
        if prct > self.lastPercent:
            print "\rFile data receving {} %                       ".format(  prct ),
            self.lastPercent = prct

    ###################
    def __endReceivingFile( self ):
        self.fh.close()
        self.fh = None
        self.fileList.pop()
        self.recvSize = 0
        self.fileSize = -1
        if len( self.fileList ) == 0:
            self.session.conn.fileMode = False
            self.session.fullDataReceived( self.finalFileList, self.extraData )