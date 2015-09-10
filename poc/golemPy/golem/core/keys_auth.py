import os
import abc
from random import random

from Crypto.PublicKey import RSA
from simplehash import SimpleHash
from crypto import mk_privkey, privtopub, ECCx
from sha3 import sha3_256
from hashlib import sha256

from golem.core.variables import KEYS_PATH, PRIVATE_KEY_PREF, PUBLIC_KEY_PREF


def sha3(seed):
    """ Return sha3-256 of seed in digest
    :param str seed: data that should be hashed
    :return str: binary hashed data
    """
    return sha3_256(seed).digest()


def sha2(seed):
    return int("0x" + sha256(seed).hexdigest(), 16)

class KeysAuth(object):
    """ Cryptographic authorization manager. Create and keeps private and public keys."""

    def __init__(self, uuid=None):
        """
        Create new keys authorization manager, load or create keys
        :param uuid|None uuid: application identifier (to read keys)
        """
        self._private_key = self._load_private_key(str(uuid))
        self.public_key = self._load_public_key(str(uuid))
        self.key_id = self.cnt_key_id(self.public_key)

    def get_difficulty(self):
        """ Count key_id difficulty in hashcash-like puzzle
        :return int: key_id difficulty
        """
        difficulty = 0
        min_hash = KeysAuth.__count_min_hash(difficulty)
        while sha2(self.key_id) <= min_hash:
            difficulty += 1
            min_hash = KeysAuth.__count_min_hash(difficulty)

        return difficulty - 1

    def get_public_key(self):
        """ Return public key """
        return self.public_key

    def get_key_id(self):
        """ Return id generated with public key """
        return self.key_id

    def cnt_key_id(self, public_key):
        """ Return id generated from given public key
        :param public_key: public key that will be used to generate id
        :return str: new id
        """
        return str(public_key)

    def encrypt(self, data, public_key=None):
        """ Encrypt given data
        :param str data: data that should be encrypted
        :param public_key: *Default: None* public key that should be used to encrypt data. If public key is None than
         default public key will be used
        :return str: encrypted data
        """
        return data

    def decrypt(self, data):
        """ Decrypt given data with default private key
        :param str data: encrypted data
        :return str: decrypted data
        """
        return data

    def sign(self, data):
        """ Sign given data with default private key
        :param str data: data to be signed
        :return: signed data
        """
        return data

    def verify(self, sig, data, public_key=None):
        """
        Verify signature
        :param str sig: signed data
        :param str data: data before signing
        :param public_key: *Default: None* public key that should be used to verify signed data. If public key is None
        then default public key will be used
        :return bool: verification result
        """
        return sig == data

    @staticmethod
    @abc.abstractmethod
    def _load_private_key(uuid):  # implement in derived classes
        return

    @staticmethod
    @abc.abstractmethod
    def _load_public_key(uuid):  # implement in derived classes
        return

    @staticmethod
    def __count_min_hash(difficulty):
        return pow(2, 256 - difficulty)


class RSAKeysAuth(KeysAuth):
    """RSA Cryptographic authorization manager. Create and keeps private and public keys based on RSA."""
    def cnt_key_id(self, public_key):
        """ Return id generated from given public key (sha1 hexdigest of openssh format).
        :param public_key: public key that will be used to generate id
        :return str: new id
        """
        return SimpleHash.hash_hex(public_key.exportKey("OpenSSH")[8:])

    def encrypt(self, data, public_key=None):
        """ Encrypt given data with RSA
        :param str data: data that should be encrypted
        :param None|_RSAobj public_key: *Default: None* public key that should be used to encrypt data.
            If public key is None than default public key will be used
        :return str: encrypted data
        """
        if public_key is None:
            public_key = self.public_key
        return public_key.encrypt(data, 32)

    def decrypt(self, data):
        """ Decrypt given data with RSA
        :param str data: encrypted data
        :return str: decrypted data
        """
        return self._private_key.decrypt(data)

    def sign(self, data):
        """ Sign given data with RSA
        :param str data: data to be signed
        :return: signed data
        """
        return self._private_key.sign(data, '')

    def verify(self, sig, data, public_key=None):
        """
        Verify the validity of an RSA signature
        :param str sig: RSA signture
        :param str data: expected data
        :param None|_RSAobj public_key: *Default: None* public key that should be used to verify signed data.
            If public key is None then default public key will be used
        :return bool: verification result
        """
        if public_key is None:
            public_key = self.public_key
        return public_key.verify(data, sig)

    @staticmethod
    def _get_private_key_loc(uuid):
        if uuid is None:
            return os.path.normpath(os.path.join(os.environ.get('GOLEM'), KEYS_PATH, "{}.pem".format(PRIVATE_KEY_PREF)))
        else:
            return os.path.normpath(os.path.join(os.environ.get('GOLEM'), KEYS_PATH,
                                                 "{}{}.pem".format(PRIVATE_KEY_PREF, uuid)))

    @staticmethod
    def _get_public_key_loc(uuid):
        if uuid is None:
            os.path.normpath(os.path.join(os.environ.get('GOLEM'), KEYS_PATH, "{}.pubkey".format(PUBLIC_KEY_PREF)))
        else:
            return os.path.normpath(os.path.join(os.environ.get('GOLEM'), KEYS_PATH,
                                                 "{}{}.pubkey".format(PUBLIC_KEY_PREF, uuid)))

    @staticmethod
    def _load_private_key(uuid=None):
        private_key = RSAKeysAuth._get_private_key_loc(uuid)
        public_key = RSAKeysAuth._get_public_key_loc(uuid)
        if not os.path.isfile(private_key) or not os.path.isfile(public_key):
            RSAKeysAuth._generate_keys(uuid)
        with open(private_key) as f:
            key = f.read()
        key = RSA.importKey(key)
        return key

    @staticmethod
    def _load_public_key(uuid=None):
        private_key = RSAKeysAuth._get_private_key_loc(uuid)
        public_key = RSAKeysAuth._get_public_key_loc(uuid)
        if not os.path.isfile(private_key) or not os.path.isfile(public_key):
            RSAKeysAuth._generate_keys(uuid)
        with open(public_key) as f:
            key = f.read()
        key = RSA.importKey(key)
        return key

    @staticmethod
    def _generate_keys(uuid):
        private_key = RSAKeysAuth._get_private_key_loc(uuid)
        public_key = RSAKeysAuth._get_public_key_loc(uuid)
        key = RSA.generate(2048)
        pub_key = key.publickey()
        with open(private_key, 'w') as f:
            f.write(key.exportKey('PEM'))
        with open(public_key, 'w') as f:
            f.write(pub_key.exportKey())


class EllipticalKeysAuth(KeysAuth):
    """Elliptical curves cryptographic authorization manager. Create and keeps private and public keys based on ECC
    (curve secp256k1)."""
    def __init__(self, uuid=None):
        """
        Create new ECC keys authorization manager, load or create keys.
        :param uuid|None uuid: application identifier (to read keys)
        """
        KeysAuth.__init__(self, uuid)
        self.ecc = ECCx(None, self._private_key)

    def cnt_key_id(self, public_key):
        """ Return id generated from given public key (in hex format).
        :param public_key: public key that will be used to generate id
        :return str: new id
        """
        return public_key.encode('hex')

    def encrypt(self, data, public_key=None):
        """ Encrypt given data with ECIES
        :param str data: data that should be encrypted
        :param None|str public_key: *Default: None* public key that should be used to encrypt data. Public key may by
        in digest (len == 64) or hexdigest (len == 128). If public key is None than default public key will be used
        :return str: encrypted data
        """
        if public_key is None:
            public_key = self.public_key
        if len(public_key) == 128:
            public_key = public_key.decode('hex')
        return ECCx.ecies_encrypt(data, public_key)

    def decrypt(self, data):
        """ Decrypt given data with ECIES
        :param str data: encrypted data
        :return str: decrypted data
        """
        return self.ecc.ecies_decrypt(data)

    def sign(self, data):
        """ Sign given data with ECDSA
        :param str data: data to be signed
        :return: signed data
        """
        return self.ecc.sign(data)

    def verify(self, sig, data, public_key=None):
        """
        Verify the validity of an ECDSA signature
        :param str sig: ECDSA signature
        :param str data: expected data
        :param None|str public_key: *Default: None* public key that should be used to verify signed data.
        Public key may be in digest (len == 64) or hexdigest (len == 128).
        If public key is None then default public key will be used.
        :return bool: verification result
        """

        if public_key is None:
            public_key = self.public_key
        if len(public_key) == 128:
            public_key = public_key.decode('hex')
        ecc = ECCx(public_key)
        return ecc.verify(sig, data)

    @staticmethod
    def _get_private_key_loc(uuid):
        if uuid is None:
            return os.path.normpath(os.path.join(os.environ.get('GOLEM'),
                                                 'examples/gnr/node_data/golem_private_key'))
        else:
            return os.path.normpath(
                os.path.join(os.environ.get('GOLEM'), 'examples/gnr/node_data/golem_private_key{}'.format(uuid)))

    @staticmethod
    def _get_public_key_loc(uuid):
        if uuid is None:
            os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples/gnr/node_data/golem_public_key'))
        else:
            return os.path.normpath(
                os.path.join(os.environ.get('GOLEM'), 'examples/gnr/node_data/golem_public_key{}'.format(uuid)))

    @staticmethod
    def _load_private_key(uuid=None):
        private_key = EllipticalKeysAuth._get_private_key_loc(uuid)
        public_key = EllipticalKeysAuth._get_public_key_loc(uuid)
        if not os.path.isfile(private_key) or not os.path.isfile(public_key):
            EllipticalKeysAuth._generate_keys(uuid)
        with open(private_key) as f:
            key = f.read()
        return key

    @staticmethod
    def _load_public_key(uuid=None):
        private_key = EllipticalKeysAuth._get_private_key_loc(uuid)
        public_key = EllipticalKeysAuth._get_public_key_loc(uuid)
        if not os.path.isfile(private_key) or not os.path.isfile(public_key):
            EllipticalKeysAuth._generate_keys(uuid)
        with open(public_key) as f:
            key = f.read()
        return key

    @staticmethod
    def _generate_keys(uuid):
        private_key = EllipticalKeysAuth._get_private_key_loc(uuid)
        public_key = EllipticalKeysAuth._get_public_key_loc(uuid)
        key = mk_privkey(str(random()))
        pub_key = privtopub(key)
        with open(private_key, 'wb') as f:
            f.write(key)
        with open(public_key, 'wb') as f:
            f.write(pub_key)


# if __name__ == "__main__":
#     auth = RSAKeysAuth()
#     # auth = EllipticalKeysAuth("BLARG")
#     print sha3(auth.get_key_id())
#     print auth._private_key
#     print auth.public_key
#     print len(auth.get_key_id())
#     print len(auth.get_key_id().decode('hex'))
#     print auth.get_public_key()
#     # print len(auth.get_public_key())
#     # print len(auth._private_key)
#     # print auth.cnt_key_id()
