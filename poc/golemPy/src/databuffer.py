import message
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

    def readUInt( self ):
        assert len( self.bufferedData ) >= 4
        (retVal,) = struct.unpack( "!L", self.bufferedData[0:4] )
        self.bufferedData = self.bufferedData[4:]

        return retVal

    def readString( self, numChars ):
        assert numChars <= len( self.bufferedData )
        retStr = self.bufferedData[:numChars]
        self.bufferedData = self.bufferedData[numChars:]

        return retStr
        
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
    print "{}".format( db.readUInt() )
