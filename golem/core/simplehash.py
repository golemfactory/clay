import hashlib
import base64


class SimpleHash(object):
    """ Hash methods wrapper meta-class """

    @classmethod
    def base64_encode(cls, data):
        """ Encode string to base64
        :param str data: binary string to be encoded
        :return str: base64-encoded string
        """
        return base64.encodestring(data)

    @classmethod
    def base64_decode(cls, data):
        """ Decode base64 string
        :param str data: base64-encoded string to be decoded
        :return str: binary string
        """
        return base64.decodestring(data)

    @classmethod
    def hash(cls, data):
        """ Return sha1 of data (digest)
        :param str data: string to be hashed
        :return str: digest sha1 of data
        """
        sha = hashlib.sha1(data)
        return sha.digest()

    @classmethod
    def hash_hex(cls, data):
        """ Return sha1 of data (hexdigest)
        :param str data: string to be hashed
        :return str: hexdigest sha1 of data
        """
        sha = hashlib.sha1(data)
        return sha.hexdigest()

    @classmethod
    def hash_base64(cls, data):
        """ Return sha1 of data encoded with base64
        :param str data: data to be hashed and encoded
        :return str: base64 encoded sha1 of data
        """
        return cls.base64_encode(cls.hash(data))

    @classmethod
    def hash_file_base64(cls, filename, block_size=2 ** 20):
        """Return sha1 of data from given file encoded with base64
        :param str filename: name of a file that should be read
        :param int block_size: *Default: 2**20* data will be read from file in chunks of this size
        :return str: base64 encoded sha1 of data from file <filename>
        """
        with open(filename, "r") as f:
            sha = hashlib.sha1()

            while True:
                data = f.read(block_size)
                if not data:
                    break
                sha.update(data)

            return cls.base64_encode(sha.digest())
