import json
import zlib
from gzip import GzipFile


def save(obj, filename):
    """Save an object to a compressed disk file. Works well with huge objects.
    :param obj: object to be serialized and saved in zip file
    :param str filename: name of a file that should be used
    be used
    """
    file_ = GzipFile(filename, 'wb')
    json.dump(obj, file_)
    file_.close()


def load(filename):
    """Loads a compressed object from disk
    :param str filename: compressed file while serialized object is saved
    :return: deserialized object that was saved in given file
    """
    file_ = GzipFile(filename, 'rb')
    obj = json.load(file_)
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
