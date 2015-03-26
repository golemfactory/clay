import struct
import cPickle as pickle

from golem.core.variables import LONG_STANDARD_SIZE

class DataConsumer:
    ###################
    def __init__( self, session, extraData ):
        self.locData = []
        self.dataSize = -1
        self.recvSize = 0

        self.session = session
        self.extraData = extraData

        self.lastPercent = 0

    ###################
    def dataReceived( self, data ):
        if self.dataSize == -1:
            self.locData.append( self.__getFirstChunk( data ) )
            self.recvSize = len( data ) - LONG_STANDARD_SIZE
        else:
            self.locData.append( data )
            self.recvSize += len( data )

        self.__printProgress()

        if self.recvSize == self.dataSize:
            self.__endReceiving()

    ###################
    def close(self):
        pass

    ###################
    def __getFirstChunk( self, data ):
        self.lastPercent = 0
        ( self.dataSize, ) = struct.unpack("!L", data[ :LONG_STANDARD_SIZE ] )
        return data[ LONG_STANDARD_SIZE: ]

    ###################
    def __printProgress( self ):
        prct = int( 100 * self.recvSize / float( self.dataSize ) )
        if prct > self.lastPercent:
            print "\rFile data receving {} %                       ".format(  prct ),
            self.lastPercent = prct

    ###################
    def __endReceiving( self ):
        self.session.conn.dataMode = False
        self.dataSize = -1
        self.recvSize = 0
        self.session.fullDataReceived( "".join(self.locData), self.extraData )
