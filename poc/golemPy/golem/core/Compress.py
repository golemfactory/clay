import cPickle
import zlib
from gzip import GzipFile

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

def compress(data):
    return zlib.compress(data)
    
def decompress(data):
    return zlib.decompress(data)

if __name__ == "__main__":
    def main():
        c = compress("12334231234434123452341234")
        with open("tezt.gz", "wb") as f:
            f.write(c)
        print c 
        d = decompress(c)
        print d

    main()