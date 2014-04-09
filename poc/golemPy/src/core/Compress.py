from gzip import GzipFile
import cPickle
import StringIO
import zlib

def save(object, filename, protocol = -1):
    """Save an object to a compressed disk file.
       Works well with huge objects.
    """
    file = GzipFile(filename, 'wb')
    cPickle.dump(object, file, protocol)
    file.close()


def load(filename):
    """Loads a compressed object from disk
    """
    file = GzipFile(filename, 'rb')
    object = cPickle.load(file)
    file.close()

    return object

def compress( data ):
    outStream = StringIO.StringIO()
    gz = GzipFile( fileobj = outStream, mode='wb'  )
    gz.write( data )
    return outStream.getvalue()
    
def decompress( data ):
    f = StringIO.StringIO( data )
    data = GzipFile(fileobj = f, mode = 'rb')
    return data.read()

if __name__ == "__main__":
    def main():
        c = compress( "12334231234434123452341234" )
        f = open( "tezt.gz", "wb")
        f.write( c )
        f.close()
        print c 
        d = decompress( c )
        print d

    main()