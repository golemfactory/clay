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
            locData = self._getFirstChunk( self.lastData + data )

        assert self.fh

        self.recvSize += len( locData )
        if self.recvSize <= self.fileSize:
            self.fh.write( locData )
            self.lastData = ''
        else:
            lastData = len( locData ) - (self.recvSize - self.fileSize)
            self.fh.write( locData[:lastData] )
            self.lastData = locData[lastData:]

        self._printProgress()

        if self.recvSize >= self.fileSize:
            self._endReceivingFile()

    def close(self):
        if self.fh is not None:
            self.fh.close()
            self.fh = None
            if self.recvSize < self.fileSize and len( self.fileList ) > 0:
                os.remove( self.fileList[-1])

    ###################
    def _getFirstChunk( self, data ):
        self.lastPercent = 0
        ( self.fileSize, ) = struct.unpack("!L", data[ :LONG_STANDARD_SIZE ] )
        logger.info( "Receiving file {}, size {}".format( self.fileList[-1], self.fileSize ) )
        assert self.fh is None

        self.fh = open( os.path.join( self.outputDir, self.fileList[-1] ), 'wb' )
        return  data[ LONG_STANDARD_SIZE: ]

    ###################
    def _printProgress( self ):
        prct = int( 100 * self.recvSize / float( self.fileSize ) )
        if prct > 100:
            prct = 100
        if prct > self.lastPercent:
            print "\rFile data receving {} %                       ".format(  prct ),
            self.lastPercent = prct

    ###################
    def _endReceivingFile( self ):
        self.fh.close()
        self.fh = None
        self.fileList.pop()
        self.recvSize = 0
        self.fileSize = -1
        if len( self.fileList ) == 0:
            self.session.conn.fileMode = False
            self.session.fullDataReceived( self.finalFileList, self.extraData )

#########################################################
class DecryptMultiFileConsumer(MultiFileConsumer):
    ###################
    def __init__( self, fileList, outputDir, session, extraData ):
        MultiFileConsumer.__init__(self, fileList, outputDir, session, extraData)
        self.chunkSize = 0
        self.recvChunkSize = 0

    ###################
    def _endReceivingFile( self ):
        self.chunkSize = 0
        self.recvChunkSize = 0
        MultiFileConsumer._endReceivingFile(self)

    ###################
    def dataReceived( self, data ):
        locData = self.lastData + data
        if self.fileSize == -1:
            locData = self._getFirstChunk( locData )

        assert self.fh

        receiveNext = False
        while not receiveNext:
            if self.chunkSize == 0:
                ( self.chunkSize, ) = struct.unpack("!L", locData[ :LONG_STANDARD_SIZE ] )
                locData = locData[LONG_STANDARD_SIZE:]

            self.recvChunkSize = len( locData )
            if self.recvChunkSize >= self.chunkSize:
                data = self.session.decrypt(locData[:self.chunkSize])
                self.fh.write(data)
                self.recvSize += len(data)
                self.lastData = locData[self.chunkSize:]
                self.recvChunkSize = 0
                self.chunkSize = 0
                locData = self.lastData

                if len(self.lastData) <= LONG_STANDARD_SIZE:
                    receiveNext = True
            else:
                self.lastData = locData
                receiveNext = True

            self._printProgress()

            if self.recvSize >= self.fileSize:
                self._endReceivingFile()
                receiveNext = True
