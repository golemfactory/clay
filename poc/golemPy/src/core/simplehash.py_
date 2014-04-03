import hashlib
import base64

class SimpleHash:

    @classmethod
    def base64_encode( cls, data ):
        return base64.encodestring( data )

    @classmethod
    def base64_decode( cls, data ):
        return base64.decodestring( data )

    @classmethod
    def hash( cls, data ):
        sha = hashlib.sha1( data )
        return sha.digest()

    @classmethod
    def hash_hex( cls, data ):
        sha = hashlib.sha1( data )
        return sha.hexdigest()

    @classmethod
    def hash_base64( cls, data ):
        return cls.base64_encode( cls.hash( data ) )

if __name__ == "__main__":
    val = "Exceptional string"

    hh = SimpleHash.hash_hex( val )
    h  = SimpleHash.hash( val )
    eh = SimpleHash.hash_base64( val )

    print "Input data '{}'".format( val )
    print "Hex encoded hash digest: {}".format( hh )
    print "Hash digest base64 encoded: {}".format( eh )
    print "Hash digest raw: {}".format( h )
    print "Hash digest raw from encode64: {}".format( SimpleHash.base64_decode( eh ) )
