import jsonpickle as json
import zlib
from gzip import GzipFile


def save(obj, filename, gzip=True):
    """Save an object to a disk file. Works well with huge objects.
    :param object obj: object to be serialized and saved
    :param str filename: filename: name of a file that should be used
    :param bool gzip: define if file should be compressed
    be used
    """
    if gzip:
        file_ = GzipFile(filename, 'wb')
    else:
        file_ = open(filename, 'wb')
    try:
        json_str = json.encode(obj)
        file_.write(json_str)
    finally:
        file_.close()


def load(filename, gzip=True):
    """Loads a compressed object from disk
    :param str filename: file while serialized object is saved
    :param bool gzip: define if file is compressed
    :return: deserialized object that was saved in given file
    """
    obj = None
    if gzip:
        file_ = GzipFile(filename, 'rb')
    else:
        file_ = open(filename, 'rb')
    try:
        json_str = file_.read()
        obj = json.decode(json_str)
    finally:
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
