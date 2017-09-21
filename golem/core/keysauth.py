import abc
import logging
import os
from _pysha3 import sha3_256 as _sha3_256
from abc import abstractmethod
from hashlib import sha256

import bitcoin
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from devp2p.crypto import ECCx, mk_privkey

from golem.core.variables import PRIVATE_KEY, PUBLIC_KEY
from golem.utils import encode_hex, decode_hex
from .simpleenv import get_local_datadir
from .simplehash import SimpleHash

logger = logging.getLogger(__name__)


def sha3(seed):
    """ Return sha3-256 (NOT keccak) of seed in digest
    :param str seed: data that should be hashed
    :return str: binary hashed data
    """
    if isinstance(seed, str):
        seed = seed.encode()
    return _sha3_256(seed).digest()


def sha2(seed):
    if isinstance(seed, str):
        seed = seed.encode()
    return int("0x" + sha256(seed).hexdigest(), 16)


def privtopub(raw_privkey):
    raw_pubkey = bitcoin.encode_pubkey(bitcoin.privtopub(raw_privkey),
                                       'bin_electrum')
    assert len(raw_pubkey) == 64
    return raw_pubkey


def get_random(min_value=0, max_value=None):
    """
    Get cryptographically secure random integer in range
    :param min_value: Minimal value
    :param max_value: Maximum value
    :return: Random number in range <min_value, max_value>
    """

    from Crypto.Random.random import randrange
    from sys import maxsize

    if max_value is None:
        max_value = maxsize
    if min_value > max_value:
        raise ArithmeticError("max_value should be greater than min_value")
    if min_value == max_value:
        return min_value
    return randrange(min_value, max_value)


def get_random_float():
    """
    Get random number in range (0, 1)
    :return: Random number in range (0, 1)
    """
    result = get_random(min_value=2)
    return float(result - 1) / float(10 ** len(str(result)))


class KeysAuth(object):
    """ Cryptographic authorization manager. Create and keeps private and public keys."""

    def __init__(self, datadir, private_key_name=PRIVATE_KEY, public_key_name=PUBLIC_KEY):
        """
        Create new keys authorization manager, load or create keys
        :param prviate_key_name str: name of the file containing private key
        :param public_key_name str: name of the file containing public key
        """
        self.get_keys_dir(datadir)
        self.private_key_name = private_key_name
        self.public_key_name = public_key_name
        self._private_key = self._load_private_key()
        self.public_key = self._load_public_key()
        self.key_id = self.cnt_key_id(self.public_key)

    def get_difficulty(self, key_id=None):
        """ Count key_id difficulty in hashcash-like puzzle
        :param str|None key_id: *Default: None* count difficulty of given key. If key_id is None then
        use default key_id
        :return int: key_id difficulty
        """
        difficulty = 0
        if key_id is None:
            key_id = self.key_id
        min_hash = KeysAuth._count_min_hash(difficulty)
        while sha2(key_id) <= min_hash:
            difficulty += 1
            min_hash = KeysAuth._count_min_hash(difficulty)

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

    @abstractmethod
    def encrypt(self, data, public_key=None):
        """ Encrypt given data
        :param str data: data that should be encrypted
        :param public_key: *Default: None* public key that should be used to encrypt data. If public key is None than
         default public key will be used
        :return str: encrypted data
        """

    @abstractmethod
    def decrypt(self, data):
        """ Decrypt given data with default private key
        :param str data: encrypted data
        :return str: decrypted data
        """

    @abstractmethod
    def sign(self, data):
        """ Sign given data with default private key
        :param str data: data to be signed
        :return: signed data
        """

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

    @abstractmethod
    def load_from_file(self, file_name):
        """ Load private key from given file. If it's proper key, then generate public key and
        save both in default files
        :param str file_name: file containing private key
        :return bool: information if keys have been changed
        """

    @abstractmethod
    def save_to_files(self, private_key_loc: str, public_key_loc: str) -> None:
        """ Save current pair of keys in given locations
        :param private_key_loc: where should private key be saved
        :param public_key_loc: where should public key be saved
        """
        pass

    @abstractmethod
    def generate_new(self, difficulty):
        """ Generate new pair of keys with given difficulty
        :param int difficulty: desired key difficulty level
        """
        pass

    @classmethod
    def get_keys_dir(cls, datadir=None):
        """ Path to the dir where keys files are stored."""
        if not hasattr(cls, '_keys_dir'):
            # TODO: Move keys to node's datadir.
            if datadir is None:
                datadir = get_local_datadir('default')
            cls._keys_dir = os.path.join(datadir, 'keys')
        if not os.path.isdir(cls._keys_dir):
            os.makedirs(cls._keys_dir)
        return cls._keys_dir

    @classmethod
    def set_keys_dir(cls, path):
        if (not os.path.isdir(path)) and os.path.exists(path):
            raise IOError("Path {} does not exists\n1){}\n2){}".format(path, os.path.isdir(path), os.path.exists(path)))
        cls._keys_dir = path

    @classmethod
    def __get_key_loc(cls, file_name):
        return os.path.join(cls.get_keys_dir(), file_name)

    @classmethod
    def _get_private_key_loc(cls, key_name):
        return cls.__get_key_loc(key_name)

    @classmethod
    def _get_public_key_loc(cls, key_name):
        return cls.__get_key_loc(key_name)

    @abc.abstractmethod
    def _load_private_key(self):  # implement in derived classes
        return

    @abc.abstractmethod
    def _load_public_key(self):  # implement in derived classes
        return

    @staticmethod
    def _count_min_hash(difficulty):
        return pow(2, 256 - difficulty)


class RSAKeysAuth(KeysAuth):
    """RSA Cryptographic authorization manager. Create and keeps private and public keys based on RSA."""

    def cnt_key_id(self, public_key):
        """ Return id generated from given public key (sha1 hexdigest of openssh format).
        :param public_key: public key that will be used to generate id
        :return str: new id
        """
        return SimpleHash.hash_hex(public_key.exportKey("OpenSSH")[8:]).encode()

    def encrypt(self, data, public_key=None):
        """ Encrypt given data with RSA
        :param str data: data that should be encrypted
        :param None|_RSAobj public_key: *Default: None* public key that should be used to encrypt data.
            If public key is None than default public key will be used
        :return str: encrypted data
        """
        if public_key is None:
            public_key = self.public_key
        return PKCS1_OAEP.new(public_key).encrypt(data)

    def decrypt(self, data):
        """ Decrypt given data with RSA
        :param str data: encrypted data
        :return str: decrypted data
        """
        return PKCS1_OAEP.new(self._private_key).decrypt(data)

    def sign(self, data):
        """ Sign given data with RSA
        :param str data: data to be signed
        :return: signed data
        """
        scheme = PKCS115_SigScheme(self._private_key)
        if scheme.can_sign():
            return scheme.sign(SHA256.new(data))
        raise RuntimeError("Cannot sign data")

    def verify(self, sig, data, public_key=None):
        """
        Verify the validity of an RSA signature
        :param str sig: RSA signature
        :param str data: expected data
        :param None|_RSAobj public_key: *Default: None* public key that should be used to verify signed data.
            If public key is None then default public key will be used
        :return bool: verification result
        """
        if public_key is None:
            public_key = self.public_key
        try:
            PKCS115_SigScheme(public_key).verify(SHA256.new(data), sig)
            return True
        except Exception as exc:
            logger.error("Cannot verify signature: {}".format(exc))
        return False

    def generate_new(self, difficulty):
        """ Generate new pair of keys with given difficulty
        :param int difficulty: desired key difficulty level
        """
        min_hash = self._count_min_hash(difficulty)
        priv_key = RSA.generate(2048)
        pub_key = str(priv_key.publickey().n)
        while sha2(pub_key) > min_hash:
            priv_key = RSA.generate(2048)
            pub_key = str(priv_key.publickey().n)
        pub_key = priv_key.publickey()
        priv_key_loc = RSAKeysAuth._get_private_key_loc(self.private_key_name)
        pub_key_loc = RSAKeysAuth._get_public_key_loc(self.public_key_name)
        with open(priv_key_loc, 'wb') as f:
            f.write(priv_key.exportKey('PEM'))
        with open(pub_key_loc, 'wb') as f:
            f.write(pub_key.exportKey())
        self.public_key = pub_key.exportKey()
        self._private_key = priv_key.exportKey('PEM')

    def load_from_file(self, file_name):
        """ Load private key from given file. If it's proper key, then generate public key and
        save both in default files
        :param str file_name: file containing private key
        :return bool: information if keys have been changed
        """
        priv_key = RSAKeysAuth._load_private_key_from_file(file_name)
        if priv_key is None:
            return False
        try:
            pub_key = priv_key.publickey()
        except (AssertionError, AttributeError):
            return False
        self._set_and_save(priv_key, pub_key)
        return True

    def save_to_files(self, private_key_loc: str, public_key_loc: str) -> None:
        """ Save current pair of keys in given locations
        :param private_key_loc: where should private key be saved
        :param public_key_loc: where should public key be saved
        """
        from os.path import isdir, dirname
        from os import mkdir

        def make_dir(file_path):
            dir_name = dirname(file_path)
            if not isdir(dir_name):
                mkdir(dir_name)

        make_dir(private_key_loc)
        make_dir(public_key_loc)

        with open(private_key_loc, 'wb') as f:
            f.write(self._private_key.exportKey('PEM'))
        with open(public_key_loc, 'wb') as f:
            f.write(self.public_key.exportKey())

    @staticmethod
    def _load_private_key_from_file(file_name):
        if not os.path.isfile(file_name):
            return None
        try:
            with open(file_name) as f:
                key = f.read()
            key = RSA.importKey(key)
        except (ValueError, IndexError, TypeError, IOError):
            return None
        return key

    def _load_private_key(self):
        private_key_loc = RSAKeysAuth._get_private_key_loc(self.private_key_name)
        public_key_loc = RSAKeysAuth._get_public_key_loc(self.public_key_name)
        if not os.path.isfile(private_key_loc) or not os.path.isfile(public_key_loc):
            RSAKeysAuth._generate_keys(private_key_loc, public_key_loc)
        with open(private_key_loc) as f:
            key = f.read()
        key = RSA.importKey(key)
        return key

    def _load_public_key(self):
        private_key_loc = RSAKeysAuth._get_private_key_loc(self.private_key_name)
        public_key_loc = RSAKeysAuth._get_public_key_loc(self.public_key_name)
        if not os.path.isfile(private_key_loc) or not os.path.isfile(public_key_loc):
            RSAKeysAuth._generate_keys(private_key_loc, public_key_loc)
        with open(public_key_loc) as f:
            key = f.read()
        key = RSA.importKey(key)
        return key

    @staticmethod
    def _generate_keys(private_key_loc, public_key_loc):
        key = RSA.generate(2048)
        pub_key = key.publickey()
        with open(private_key_loc, 'wb') as f:
            f.write(key.exportKey('PEM'))
        with open(public_key_loc, 'wb') as f:
            f.write(pub_key.exportKey())

    def _set_and_save(self, private_key, public_key):
        self._private_key = private_key
        self.public_key = public_key
        self.key_id = self.cnt_key_id(self.public_key)
        private_key_loc = RSAKeysAuth._get_private_key_loc(self.private_key_name)
        public_key_loc = RSAKeysAuth._get_public_key_loc(self.public_key_name)
        with open(private_key_loc, 'wb') as f:
            f.write(private_key.exportKey('PEM'))
        with open(public_key_loc, 'wb') as f:
            f.write(public_key.exportKey())


class EllipticalKeysAuth(KeysAuth):
    """Elliptical curves cryptographic authorization manager. Create and keeps private and public keys based on ECC
    (curve secp256k1)."""

    def __init__(self, datadir, private_key_name=PRIVATE_KEY, public_key_name=PUBLIC_KEY):
        """
        Create new ECC keys authorization manager, load or create keys.
        :param uuid|None uuid: application identifier (to read keys)
        """
        KeysAuth.__init__(self, datadir, private_key_name, public_key_name)
        try:
            self.ecc = ECCx(None, self._private_key)
        except AssertionError:
            private_key_loc = self._get_private_key_loc(private_key_name)
            public_key_loc = self._get_public_key_loc(public_key_name)
            self._generate_keys(private_key_loc, public_key_loc)

    def cnt_key_id(self, public_key):
        """ Return id generated from given public key (in hex format).
        :param public_key: public key that will be used to generate id
        :return str: new id
        """
        return encode_hex(public_key)

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
            public_key = decode_hex(public_key)
        return ECCx.ecies_encrypt(data, public_key)

    def decrypt(self, data):
        """ Decrypt given data with ECIES
        :param str data: encrypted data
        :return str: decrypted data
        """
        return self.ecc.ecies_decrypt(data)

    def sign(self, data):
        """ Sign given data with ECDSA
        sha3 is used to shorten the data and speedup calculations
        :param str data: data to be signed
        :return: signed data
        """
        return self.ecc.sign(sha3(data))

    def verify(self, sig, data, public_key=None):
        """
        Verify the validity of an ECDSA signature
        sha3 is used to shorten the data and speedup calculations
        :param str sig: ECDSA signature
        :param str data: expected data
        :param None|str public_key: *Default: None* public key that should be used to verify signed data.
        Public key may be in digest (len == 64) or hexdigest (len == 128).
        If public key is None then default public key will be used.
        :return bool: verification result
        """

        try:
            if public_key is None:
                public_key = self.public_key
            if len(public_key) == 128:
                public_key = decode_hex(public_key)
            ecc = ECCx(public_key)
            return ecc.verify(sig, sha3(data))
        except AssertionError:
            logger.info("Wrong key format")
        except Exception as exc:
            logger.error("Cannot verify signature: {}".format(exc))
        return False

    def generate_new(self, difficulty):
        """ Generate new pair of keys with given difficulty
        :param int difficulty: desired key difficulty level
        :raise TypeError: in case of incorrect @difficulty type
        """
        if not isinstance(difficulty, int):
            raise TypeError("Incorrect 'difficulty' type: {}".format(type(difficulty)))
        min_hash = self._count_min_hash(difficulty)
        priv_key = mk_privkey(str(get_random_float()))
        pub_key = privtopub(priv_key)
        while sha2(self.cnt_key_id(pub_key)) > min_hash:
            priv_key = mk_privkey(str(get_random_float()))
            pub_key = privtopub(priv_key)
        self._set_and_save(priv_key, pub_key)

    def load_from_file(self, file_name):
        """ Load private key from given file. If it's proper key, then generate public key and
        save both in default files
        :param str file_name: file containing private key
        :return bool: information if keys have been changed
        """
        priv_key = EllipticalKeysAuth._load_private_key_from_file(file_name)
        if priv_key is None:
            return False
        try:
            pub_key = privtopub(priv_key)
        except AssertionError:
            return False
        self._set_and_save(priv_key, pub_key)
        return True

    def save_to_files(self, private_key_loc: str, public_key_loc: str) -> None:
        """ Save current pair of keys in given locations
        :param private_key_loc: where should private key be saved
        :param public_key_loc: where should public key be saved
        """
        with open(private_key_loc, 'wb') as f:
            f.write(self._private_key)
        with open(public_key_loc, 'wb') as f:
            f.write(self.public_key)

    def _set_and_save(self, priv_key, pub_key):
        priv_key_loc = EllipticalKeysAuth._get_private_key_loc(self.private_key_name)
        pub_key_loc = EllipticalKeysAuth._get_public_key_loc(self.public_key_name)
        self._private_key = priv_key
        self.public_key = pub_key
        self.key_id = self.cnt_key_id(pub_key)
        self.save_to_files(priv_key_loc, pub_key_loc)
        self.ecc = ECCx(None, self._private_key)

    @staticmethod
    def _load_private_key_from_file(file_name):
        if not os.path.isfile(file_name):
            return None
        with open(file_name, 'rb') as f:
            key = f.read()
        return key

    def _load_private_key(self):
        private_key_loc = EllipticalKeysAuth._get_private_key_loc(self.private_key_name)
        public_key_loc = EllipticalKeysAuth._get_public_key_loc(self.public_key_name)
        if not os.path.isfile(private_key_loc) or not os.path.isfile(public_key_loc):
            EllipticalKeysAuth._generate_keys(private_key_loc, public_key_loc)
        with open(private_key_loc, 'rb') as f:
            key = f.read()
        return key

    def _load_public_key(self):
        private_key_loc = EllipticalKeysAuth._get_private_key_loc(self.private_key_name)
        public_key_loc = EllipticalKeysAuth._get_public_key_loc(self.public_key_name)
        if not os.path.isfile(private_key_loc) or not os.path.isfile(public_key_loc):
            EllipticalKeysAuth._generate_keys(private_key_loc, public_key_loc)
        with open(public_key_loc, 'rb') as f:
            key = f.read()
        return key

    @staticmethod
    def _generate_keys(private_key_loc, public_key_loc):
        key = mk_privkey(str(get_random_float()))
        pub_key = privtopub(key)

        # Create dir for the keys.
        # FIXME: It assumes private and public keys are stored in the same dir.
        # FIXME: The same fix is needed for RSAKeysAuth.
        keys_dir = os.path.dirname(private_key_loc)
        if not os.path.isdir(keys_dir):
            os.makedirs(keys_dir, 0o700)

        with open(private_key_loc, 'wb') as f:
            f.write(key)
        with open(public_key_loc, 'wb') as f:
            f.write(pub_key)
