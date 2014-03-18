import struct

class DataBuffer:

    def __init__( self ):
        self.bufferedData = ""
   
    def appendUInt( self, num ):
        assert num >= 0
        strNumRep = struct.pack( "!L", num )
        self.bufferedData = "".join( [ self.bufferedData, strNumRep ] )

    def appendString( self, data ):
        self.bufferedData = "".join( [ self.bufferedData, data ] )

    def dataSize( self ):
        return len( self.bufferedData )

    def peekUInt( self ):
        assert len( self.bufferedData ) >= 4

        (retVal,) = struct.unpack( "!L", self.bufferedData[0:4] )
        return retVal

    def readUInt( self ):
        val = self.peekUInt()
        self.bufferedData = self.bufferedData[4:]

        return val

    def peekString( self, numChars ):
        assert numChars <= len( self.bufferedData )

        retStr = self.bufferedData[:numChars]
        return retStr

    def readString( self, numChars ):
        val = self.peekString( numChars )
        self.bufferedData = self.bufferedData[numChars:]

        return val
        
    def readAll( self ):
        retData = self.bufferData
        self.bufferedData = ""

        return retData

    def readLenPrefixedString( self ):
        retStr = None

        if self.dataSize() > 4 and self.dataSize() >= ( self.peekUInt() + 4 ):
            retStr = self.readString( self.readUInt() )

        return retStr

    def appendLenPrefixedString( self, data ):
        self.appendUInt( len( data ) )
        self.appendString( data )

if __name__ == "__main__":

    db = DataBuffer()

    val = 1512
    db.appendUInt( val )
    print "Written {} Buffer len {}".format( val, db.dataSize() )

    val = 27815
    db.appendUInt( val )
    print "Written {} Buffer len {}".format( val, db.dataSize() )

    val = "string0"
    s1l = len( val )
    db.appendString( val  )
    print "Written '{}' Buffer len {}".format( val, db.dataSize() )

    val = "stringofsizegreaterthan1"
    s2l = len( val )
    db.appendString( val )
    print "Buffer '{}' len {}".format( val, db.dataSize() )

    val = db.readUInt()
    print "Read uint {} len remaining {}".format( val, db.dataSize() )

    val = db.readUInt()
    print "Read uint {} len remaining {}".format( val, db.dataSize() )

    val = db.readString( s1l )
    print "Read string '{}' len remaining {}".format( val, db.dataSize() )

    val = db.readString( s2l )
    print "Read string '{}' len remaining {}".format( val, db.dataSize() )

    print "{}".format( db.readString( 0 ) )
    #expected to fail on assert
    #print "{}".format( db.readUInt() )


    s3 = "test string 3"
    s4 = "not a very test string"

    db.appendLenPrefixedString( s3 )
    db.appendLenPrefixedString( s4 )

    print db.readLenPrefixedString()
    print db.dataSize()
    print db.readLenPrefixedString()
    print db.dataSize()
