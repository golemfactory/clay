import abc
from hashlib import sha256
from Crypto.Cipher import AES
from Crypto import Random
from Crypto.Random.random import StrongRandom
from threading import Lock


class abstractclassmethod(classmethod):

    __isabstractmethod__ = True

    def __init__(self, func):
        func.__isabstractmethod__ = True
        super(abstractclassmethod, self).__init__(func)


class FileHelper(object):

    def __init__(self, param, mode):
        self.param = param
        self.mode = mode
        self.obj = None

    def __enter__(self):
        if isinstance(self.param, file):
            self.obj = self.param
        else:
            self.obj = open(self.param, self.mode)
        return self.obj

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.obj.__exit__(self, exc_type, exc_val, exc_tb)


class FileEncryptor(object):

    __metaclass__ = abc.ABCMeta

    __strong_random = StrongRandom()
    __lock = Lock()

    @classmethod
    def gen_secret(cls, min_length, max_length):
        with cls.__lock:
            n_chars = cls.__strong_random.randrange(min_length, max_length)
            return Random.new().read(n_chars)

    @abstractclassmethod
    def encrypt(cls, file_in, file_out, key_or_secret):
        pass

    @abstractclassmethod
    def decrypt(cls, file_in, file_out, key_or_secret):
        pass


class AESFileEncryptor(FileEncryptor):

    aes_mode = AES.MODE_CBC
    block_size = AES.block_size
    chunk_size = 1024
    salt_prefix = 'salt_'
    salt_prefix_len = len(salt_prefix)

    @classmethod
    def gen_salt(cls, length):
        return Random.new().read(length - cls.salt_prefix_len)

    @classmethod
    def get_key_and_iv(cls, secret, salt, key_len, iv_len):

        total_len = key_len + iv_len
        digest = chunk = str()

        while len(digest) < total_len:
            chunk = sha256(chunk + secret + salt).digest()
            digest += chunk

        return digest[:key_len], digest[key_len:total_len]

    @classmethod
    def encrypt(cls, file_in, file_out, secret, key_len=32):

        block_size = cls.block_size
        salt = cls.gen_salt(block_size)
        key, iv = cls.get_key_and_iv(secret, salt, key_len, block_size)
        cipher = AES.new(key, cls.aes_mode, iv)

        with FileHelper(file_in, 'rb') as src, FileHelper(file_out, 'wb') as dst:

            dst.write(cls.salt_prefix + salt)

            working = True
            while working:

                chunk = src.read(cls.chunk_size * block_size)
                chunk_len = len(chunk)
                chunk_len_mod = chunk_len % block_size

                if chunk_len == 0 or chunk_len_mod != 0:
                    pad_len = (block_size - chunk_len_mod) or block_size
                    chunk += pad_len * chr(pad_len)
                    working = False

                dst.write(cipher.encrypt(chunk))

    @classmethod
    def decrypt(cls, file_in, file_out, secret, key_len=32):

        block_size = cls.block_size

        with FileHelper(file_in, 'rb') as src, FileHelper(file_out, 'wb') as dst:

            block = src.read(block_size)
            salt = block[cls.salt_prefix_len:]

            key, iv = cls.get_key_and_iv(secret, salt, key_len, block_size)
            cipher = AES.new(key, cls.aes_mode, iv)

            working = True
            next_chunk = str()
            while working:

                chunk = next_chunk
                next_chunk = cipher.decrypt(src.read(cls.chunk_size *
                                                     block_size))
                if len(next_chunk) == 0:
                    pad_len = ord(chunk[-1])
                    chunk = chunk[:-pad_len]
                    working = False

                dst.write(chunk)
