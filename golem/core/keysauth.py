import logging
import math
import os
from abc import abstractmethod
from datetime import datetime
from hashlib import sha256
from typing import Optional, Tuple, Union

from golem_messages.cryptography import ECCx, mk_privkey, ecdsa_verify, \
    privtopub

from _pysha3 import sha3_256 as _sha3_256

from golem.core.variables import PRIVATE_KEY, PUBLIC_KEY
from golem.utils import encode_hex, decode_hex
from .simpleenv import get_local_datadir

IntFloatT = Union[int, float]

logger = logging.getLogger(__name__)


def sha3(seed: Union[str, bytes]) -> bytes:
    """ Return sha3-256 (NOT keccak) of seed in digest
    :param seed: data that should be hashed
    :return: binary hashed data
    """
    if isinstance(seed, str):
        seed = seed.encode()
    return _sha3_256(seed).digest()


def sha2(seed: Union[str, bytes]) -> int:
    if isinstance(seed, str):
        seed = seed.encode()
    return int.from_bytes(sha256(seed).digest(), 'big')


def get_random(min_value: int = 0, max_value: int = None) -> int:
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


def get_random_float() -> float:
    """
    Get random number in range (0, 1)
    :return: Random number in range (0, 1)
    """
    result = get_random(min_value=2)
    return float(result - 1) / float(10 ** len(str(result)))


class EllipticalKeysAuth:
    """
    Elliptical curves cryptographic authorization manager. Create and keeps
    private and public keys based on ECC (curve secp256k1).
    """
    PRIV_KEY_LEN = 32
    PUB_KEY_LEN = 64
    HEX_PUB_KEY_LEN = 128
    KEY_ID_LEN = 128

    _private_key_loc = ""  # type: str
    _public_key_loc = ""  # type: str
    _private_key = b''  # type: bytes
    public_key = b''  # type: bytes
    key_id = ""  # type: str
    ecc = None  # type: ECCx

    def __init__(
            self,
            data_dir: str,
            private_key_name: str = PRIVATE_KEY,
            public_key_name: str = PUBLIC_KEY,
            difficulty: IntFloatT = 0):
        """
        Create new ECC keys authorization manager, load or create keys.

        :param prviate_key_name: name of the file containing private key
        :param public_key_name: name of the file containing public key
        :param difficulty:
            desired key difficulty level.
            It's a number of leading zeros in binary representation of
            public key. Works with floats too.
            Value in range <0, 256>. 0 is not difficult.
            Maximum is impossible.
        """

        # Gather and validate all required data
        # 'self' is not constructed yet, so don't use it.

        if not data_dir:
            data_dir = get_local_datadir('default')
        keys_dir = os.path.join(data_dir, 'keys')
        if not os.path.isdir(keys_dir):
            os.makedirs(keys_dir)

        private_key_loc = EllipticalKeysAuth._get_key_loc(
            keys_dir, private_key_name)
        public_key_loc = EllipticalKeysAuth._get_key_loc(
            keys_dir, public_key_name)

        loaded_keys = EllipticalKeysAuth._load_and_check_keys(
            private_key_loc, public_key_loc, difficulty)
        if loaded_keys:
            priv_key, pub_key = loaded_keys
        else:
            logger.info("Backing up existing keys and creating new key pair.")
            EllipticalKeysAuth._backup_keys(private_key_loc, public_key_loc)
            priv_key, pub_key = \
                EllipticalKeysAuth._generate_new_keys(difficulty)

        # Everything is clear. Store gathered data in 'self'.

        self._private_key_loc = private_key_loc
        self._public_key_loc = public_key_loc
        self._set_keys(priv_key, pub_key)
        self.difficulty = difficulty

        if not loaded_keys:
            self._save_keys()

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
            raise IOError("Path {} does not exists\n1){}\n2){}".format(
                path, os.path.isdir(path), os.path.exists(path)))
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

    @abstractmethod
    def _load_private_key(self):  # implement in derived classes
        return

    @abstractmethod
    def _load_public_key(self):  # implement in derived classes
        return

    @staticmethod
    def _backup_keys(
            private_key_loc: str,
            public_key_loc: str):

        def backup_file(path, date):
            if os.path.exists(path):
                dirname, basename = os.path.split(path)
                dest_path = os.path.join(
                    dirname, basename.replace('.', '_') + '_' + date + '.bak')
                os.rename(path, dest_path)

        # Windows doesn't like ':' in filenames
        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        backup_file(private_key_loc, date)
        backup_file(public_key_loc, date)

    @staticmethod
    def _load_and_check_keys(
            private_key_loc: str,
            public_key_loc: Optional[str],
            difficulty: IntFloatT) \
            -> Optional[Tuple[bytes, bytes]]:

        try:
            with open(private_key_loc, 'rb') as f:
                priv_key = f.read()
            pub_key = None
            if public_key_loc:
                with open(public_key_loc, 'rb') as f:
                    pub_key = f.read()
        except FileNotFoundError:
            return None

        if not len(priv_key) == EllipticalKeysAuth.PRIV_KEY_LEN:
            logger.error("Unexpected private key size: %d. "
                         "Will create new keys.", len(priv_key))
            return None

        if public_key_loc:
            if not len(pub_key) == EllipticalKeysAuth.PUB_KEY_LEN:
                logger.error("Unexpected public key size: %d. "
                             "Will create new keys.", len(pub_key))
                return None

            if not privtopub(priv_key) == pub_key:
                logger.error("Public key does not match private key."
                             "Will create new keys.")
                return None
        else:
            pub_key = privtopub(priv_key)

        if not EllipticalKeysAuth.is_pubkey_difficult(pub_key, difficulty):
            logger.warning("Current key is not difficult enough. "
                           "Will create new keys.")
            return None

        return (priv_key, pub_key)

    def _set_keys(self, priv_key: bytes, pub_key: bytes) -> None:
        self._private_key = priv_key
        self.public_key = pub_key
        self.key_id = encode_hex(pub_key)
        self.ecc = ECCx(raw_privkey=priv_key)

    @staticmethod
    def _get_key_loc(keys_dir: str, file_name: str) -> str:
        return os.path.join(keys_dir, file_name)

    def encrypt(self, data: bytes, public_key: Optional[bytes] = None) -> bytes:
        """ Encrypt given data with ECIES
        :param data: data that should be encrypted
        :param public_key: *Default: None* public key that should be used to
                           encrypt data. Public key may be in digest (len == 64)
                           or hexdigest (len == 128).
        If public key is None then default public key will be used.
        :return: encrypted data
        """
        if public_key is None:
            public_key = self.public_key
        if len(public_key) == EllipticalKeysAuth.HEX_PUB_KEY_LEN:
            public_key = decode_hex(public_key)
        return ECCx.ecies_encrypt(data, public_key)

    def decrypt(self, data: bytes) -> bytes:
        """ Decrypt given data with ECIES
        :param data: encrypted data
        :return: decrypted data
        """
        return self.ecc.ecies_decrypt(data)

    def sign(self, data: bytes) -> bytes:
        """ Sign given data with ECDSA
        sha3 is used to shorten the data and speedup calculations
        :param data: data to be signed
        :return: signed data
        """
        return self.ecc.sign(data)

    def verify(self, sig: bytes, data: bytes,
               public_key: Optional[bytes] = None) -> bool:
        """
        Verify the validity of an ECDSA signature
        sha3 is used to shorten the data and speedup calculations
        :param sig: ECDSA signature
        :param data: expected data
        :param public_key: *Default: None* public key that should be used to
                           verify signed data.
        Public key may be in digest (len == 64) or hexdigest (len == 128).
        If public key is None then default public key will be used.
        :return bool: verification result
        """

        try:
            if public_key is None:
                public_key = self.public_key
            if len(public_key) == EllipticalKeysAuth.HEX_PUB_KEY_LEN:
                public_key = decode_hex(public_key)
            return ecdsa_verify(public_key, sig, data)
        except AssertionError:
            logger.info("Wrong key format")
        except Exception as exc:
            logger.error("Cannot verify signature: {}".format(exc))
        return False

    @staticmethod
    def _count_max_hash(difficulty: IntFloatT) -> int:
        return pow(2, 256-difficulty)

    @staticmethod
    def _is_pubkey_difficult(pub_key: bytes, max_hash: int) -> bool:
        return sha2(pub_key) < max_hash

    @staticmethod
    def is_pubkey_difficult(pub_key: Union[bytes, str],
                            difficulty: IntFloatT) -> bool:
        if isinstance(pub_key, str):
            pub_key = decode_hex(pub_key)
        max_hash = EllipticalKeysAuth._count_max_hash(difficulty)
        return EllipticalKeysAuth._is_pubkey_difficult(pub_key, max_hash)

    def is_difficult(self, difficulty: IntFloatT) -> bool:
        return self.is_pubkey_difficult(self.public_key, difficulty)

    @staticmethod
    def _generate_new_keys(difficulty: IntFloatT) -> (bytes, bytes):
        if not isinstance(difficulty, (int, float)):
            raise TypeError("Incorrect 'difficulty' type: {}"
                            .format(type(difficulty)))

        max_hash = EllipticalKeysAuth._count_max_hash(difficulty)

        while True:
            priv_key = mk_privkey(str(get_random_float()))
            pub_key = privtopub(priv_key)
            if EllipticalKeysAuth._is_pubkey_difficult(pub_key, max_hash):
                break
        return (priv_key, pub_key)

    def generate_new(self, difficulty: IntFloatT) -> None:
        """ Generate new pair of keys with given difficulty

        :param difficulty: see __init__
        :raise TypeError: in case of incorrect @difficulty type
        """
        priv_key, pub_key = self._generate_new_keys(difficulty)
        self._set_keys(priv_key, pub_key)
        EllipticalKeysAuth._backup_keys(
            self._private_key_loc, self._public_key_loc)
        self._save_keys()

    def get_difficulty(self, key_id: Optional[str] = None) -> float:
        """
        Calculate key's difficulty.
        This is more expensive to calculate than is_difficult, so use
        the latter if you can.

        :param key_id: *Default: None* count difficulty of given key.
                       If key_id is None then use default key_id
        :return: key_id difficulty
        """
        pub_key = decode_hex(key_id) if key_id else self.public_key
        return 256 - math.log2(sha2(pub_key))

    def load_from_file(self, file_name: str) -> bool:
        """ Load private key from given file. If it's proper key, then generate
        public key and save both in default files
        :param file_name: file containing private key
        :return: information if keys have been changed
        """
        keys = EllipticalKeysAuth._load_and_check_keys(
            file_name, None, self.difficulty)

        if not keys:
            return False

        self._set_keys(*keys)
        EllipticalKeysAuth._backup_keys(
            self._private_key_loc, self._public_key_loc)
        self._save_keys()
        return True

    def save_to_files(self, private_key_loc: str, public_key_loc: str) -> bool:
        """ Save current pair of keys in given locations
        :param private_key_loc: where should private key be saved
        :param public_key_loc: where should public key be saved
        :return: return True if keys have been saved, False otherwise
        """
        try:
            with open(private_key_loc, 'wb') as f:
                f.write(self._private_key)
            with open(public_key_loc, 'wb') as f:
                f.write(self.public_key)
            return True
        except IOError:
            return False

    def _save_keys(self):
        with open(self._private_key_loc, 'wb') as f:
            f.write(self._private_key)
        with open(self._public_key_loc, 'wb') as f:
            f.write(self.public_key)
