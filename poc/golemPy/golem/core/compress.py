import cPickle
import zlib
from gzip import GzipFile


def save(obj, filename, protocol=-1):
    """Save an object to a compressed disk file. Works well with huge objects.
    :param obj: object to be serialized and saved in zip file
    :param str filename: name of a file that should be used
    :param int protocol: *Default: -1* pickle protocol version. If protocol is -1 then highest protocol version will
    be used
    """
    file_ = GzipFile(filename, 'wb')
    cPickle.dump(obj, file_, protocol)
    file_.close()


def load(filename):
    """Loads a compressed object from disk
    :param str filename: compressed file while serialized object is saved
    :return: deserialized object that was saved in given file
    """
    file_ = GzipFile(filename, 'rb')
    obj = cPickle.load(file_)
    file_.close()

    return obj


def compress(data):
    """ Compress given data
    :param str data: the data in string
    :return str: string contained compressed data
    """
    return zlib.compress(data)


def decompress(data):
    """
    Decompress the data
    :param str data: data to be decompressed
    :return str: string containing uncompressed data
    """
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
