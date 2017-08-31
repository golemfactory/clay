import zlib


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
