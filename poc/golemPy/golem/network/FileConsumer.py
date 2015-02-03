import struct

from golem.core.variables import LONG_STANDARD_SIZE
from golem.resource.Resource import decompressDir

class FileConsumer:
    ###################
    def __init__( self, tmpFile, outputDir, session, extraData ):
        self.fh = None
        self.fileSize = -1
        self.recvSize = 0

        self.tmpFile = tmpFile
        self.outputDir = outputDir

        self.session = session
        self.extraData = extraData

        self.lastPercent = 0

    ###################
    def dataReceived( self, data ):
        locData = data
        if self.fileSize == -1:
            locData = self.__getFirstChunk( data )

        assert self.fh

        self.recvSize += len( locData )
        self.fh.write( locData )

        self.__printProgress()

        if self.recvSize == self.fileSize:
            self.__endReceiving()

    ###################
    def __getFirstChunk( self, data ):
        self.lastPercent = 0
        ( self.fileSize, ) = struct.unpack("!L", data[ :LONG_STANDARD_SIZE ] )
        assert self.fh is None

        self.fh = open( self.tmpFile, 'wb' )
        return  data[ LONG_STANDARD_SIZE: ]

    ###################
    def __printProgress( self ):
        prct = int( 100 * self.recvSize / float( self.fileSize ) )
        if prct > self.lastPercent:
            print "\rFile data receving {} %                       ".format(  prct ),
            self.lastPercent = prct

    ###################
    def __endReceiving( self ):
        self.session.conn.fileMode = False
        self.fh.close()
        self.fh = None
        if self.fileSize > 0:
            decompressDir( self.outputDir, self.tmpFile )
        self.session.fullFileReceived( self.extraData )
        self.fileSize = -1
        self.recvSize = 0
