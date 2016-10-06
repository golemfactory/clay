import os
import abc
import logging
from random import random

from Crypto.PublicKey import RSA
from simpleenv import get_local_datadir
from simplehash import SimpleHash
from devp2p.crypto import mk_privkey, privtopub, ECCx
from sha3 import sha3_256
from hashlib import sha256

from golem.core.variables import PRIVATE_KEY, PUBLIC_KEY


logger = logging.getLogger(__name__)


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

    @abc.abstractmethod
    def load_from_file(self, file_name):
        """ Load private key from given file. If it's proper key, then generate public key and
        save both in default files
        :param str file_name: file containing private key
        :return bool: information if keys have been changed
        """

    @abc.abstractmethod
    def save_to_files(self, private_key_loc, public_key_loc):
        """ Save current pair of keys in given locations
        :param str private_key_loc: where should private key be saved
        :param str public_key_loc: where should public key be saved
        :return boolean: return True if keys have been saved, False otherwise
        """
        pass

    @abc.abstractmethod
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
        assert os.path.isdir(path) or not os.path.exists(path)
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
        :param str sig: RSA signature
        :param str data: expected data
        :param None|_RSAobj public_key: *Default: None* public key that should be used to verify signed data.
            If public key is None then default public key will be used
        :return bool: verification result
        """
        if public_key is None:
            public_key = self.public_key
        try:
            return public_key.verify(data, sig)
        except Exception as exc:
            logger.error("Cannot verify signature: {}".format(exc))
        return False

    def generate_new(self, difficulty):
        """ Generate new pair of keys with given difficulty
        :param int difficulty: desired key difficulty level
        """
        min_hash = self._count_min_hash(difficulty)
        priv_key = RSA.generate(2048)
        pub_key = priv_key.publickey()
        while sha2(pub_key) > min_hash:
            priv_key = RSA.generate(2048)
            pub_key = priv_key.publickey()
        priv_key_loc = RSAKeysAuth._get_private_key_loc(self.private_key_name)
        pub_key_loc = RSAKeysAuth._get_public_key_loc(self.public_key_name)
        with open(priv_key_loc, 'w') as f:
            f.write(priv_key.exportKey('PEM'))
        with open(pub_key_loc, 'w') as f:
            f.write(pub_key.exportKey())

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

    def save_to_files(self, private_key_loc, public_key_loc):
        """ Save current pair of keys in given locations
        :param str private_key_loc: where should private key be saved
        :param str public_key_loc: where should public key be saved
        :return boolean: return True if keys have been saved, False otherwise
        """
        try:
            with open(private_key_loc, 'w') as f:
                f.write(self._private_key.exportKey('PEM'))
            with open(public_key_loc, 'w') as f:
                f.write(self.public_key.exportKey())
                return True
        except IOError:
            return False

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
        with open(private_key_loc, 'w') as f:
            f.write(key.exportKey('PEM'))
        with open(public_key_loc, 'w') as f:
            f.write(pub_key.exportKey())

    def _set_and_save(self, private_key, public_key):
        self._private_key = private_key
        self.public_key = public_key
        self.key_id = self.cnt_key_id(self.public_key)
        private_key_loc = RSAKeysAuth._get_private_key_loc(self.private_key_name)
        public_key_loc = RSAKeysAuth._get_public_key_loc(self.public_key_name)
        with open(private_key_loc, 'w') as f:
            f.write(private_key.exportKey('PEM'))
        with open(public_key_loc, 'w') as f:
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
        return self.ecc.sign(sha3(data))

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

        try:
            if public_key is None:
                public_key = self.public_key
            if len(public_key) == 128:
                public_key = public_key.decode('hex')
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
        """
        min_hash = self._count_min_hash(difficulty)
        priv_key = mk_privkey(str(random()))
        pub_key = privtopub(priv_key)
        while sha2(self.cnt_key_id(pub_key)) > min_hash:
            priv_key = mk_privkey(str(random()))
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

    def save_to_files(self, private_key_loc, public_key_loc):
        """ Save current pair of keys in given locations
        :param str private_key_loc: where should private key be saved
        :param str public_key_loc: where should public key be saved
        :return boolean: return True if keys have been saved, False otherwise
        """
        try:
            with open(private_key_loc, 'wb') as f:
                f.write(self._private_key)
            with open(public_key_loc, 'wb') as f:
                f.write(self.public_key)
            return True
        except IOError:
            return False

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
        with open(file_name) as f:
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
        key = mk_privkey(str(random()))
        pub_key = privtopub(key)

        # Create dir for the keys.
        # FIXME: It assumes private and public keys are stored in the same dir.
        # FIXME: The same fix is needed for RSAKeysAuth.
        keys_dir = os.path.dirname(private_key_loc)
        if not os.path.isdir(keys_dir):
            os.makedirs(keys_dir, 0700)

        with open(private_key_loc, 'wb') as f:
            f.write(key)
        with open(public_key_loc, 'wb') as f:
            f.write(pub_key)
