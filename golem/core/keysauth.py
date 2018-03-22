import json
import logging
import math
import os
import sys
import time
from hashlib import sha256
from typing import Optional, Tuple, Union

import ethereum.keys
from ethereum.keys import decode_keystore_json, make_keystore_json
from golem_messages.cryptography import ECCx, mk_privkey, ecdsa_verify, \
    privtopub

from golem.utils import encode_hex, decode_hex

logger = logging.getLogger(__name__)


def sha2(seed: Union[str, bytes]) -> int:
    if isinstance(seed, str):
        seed = seed.encode()
    return int.from_bytes(sha256(seed).digest(), 'big')


def get_random(min_value: int = 0, max_value: int = sys.maxsize) -> int:
    """
    :return: Random cryptographically secure random integer in range
             `<min_value, max_value>`
    """

    from Crypto.Random.random import randrange  # noqa pylint: disable=no-name-in-module,import-error
    if min_value > max_value:
        raise ArithmeticError("max_value should be greater than min_value")
    if min_value == max_value:
        return min_value

    return randrange(min_value, max_value)


def get_random_float() -> float:
    """
    :return: Random number in range (0, 1)
    """

    random = get_random(min_value=1, max_value=sys.maxsize - 1)
    return float(random) / sys.maxsize


def _serialize_keystore(keystore):
    def encode_bytes(obj):
        if isinstance(obj, bytes):
            return ''.join([chr(c) for c in obj])
        if isinstance(obj, dict):
            for k, v in obj.items():
                obj[k] = encode_bytes(v)
        return obj

    return json.dumps(encode_bytes(keystore))


class WrongPassword(Exception):
    pass


class KeysAuth:
    """
    Elliptical curves cryptographic authorization manager. Generates
    private and public keys based on ECC (curve secp256k1) with specified
    difficulty. Private key is stored in file. When this file not exist, is
    broken or contain key below requested difficulty new key is generated.
    """
    KEYS_SUBDIR = 'keys'

    _private_key: bytes = b''
    public_key: bytes = b''
    key_id: str = ""
    ecc: ECCx = None

    def __init__(self, datadir: str, private_key_name: str, password: str,
                 difficulty: int = 0) -> None:
        """
        Create new ECC keys authorization manager, load or create keys.

        :param datadir where to store files
        :param private_key_name: name of the file containing private key
        :param password: user password to protect private key
        :param difficulty:
            desired key difficulty level. It's a number of leading zeros in
            binary representation of public key. Value in range <0, 255>.
            0 accepts all keys, 255 is nearly impossible.
        """

        prv, pub = KeysAuth._load_or_generate_keys(
            datadir, private_key_name, password, difficulty)

        self._private_key = prv
        self.ecc = ECCx(prv)
        self.public_key = pub
        self.key_id = encode_hex(pub)
        self.difficulty = KeysAuth.get_difficulty(self.key_id)

    @staticmethod
    def key_exists(datadir: str, private_key_name: str) -> bool:
        keys_dir = KeysAuth._get_or_create_keys_dir(datadir)
        priv_key_path = os.path.join(keys_dir, private_key_name)
        return os.path.isfile(priv_key_path)

    @staticmethod
    def _load_or_generate_keys(datadir: str, filename: str, password: str,
                               difficulty: int) -> Tuple[bytes, bytes]:
        keys_dir = KeysAuth._get_or_create_keys_dir(datadir)
        priv_key_path = os.path.join(keys_dir, filename)

        loaded_keys = KeysAuth._load_and_check_keys(
            priv_key_path,
            password,
            difficulty,
        )

        if loaded_keys:
            priv_key, pub_key = loaded_keys
        else:
            priv_key, pub_key = KeysAuth._generate_keys(difficulty)
            KeysAuth._save_private_key(priv_key, priv_key_path, password)

        return priv_key, pub_key

    @staticmethod
    def _get_or_create_keys_dir(datadir: str) -> str:
        keys_dir = os.path.join(datadir, KeysAuth.KEYS_SUBDIR)
        if not os.path.isdir(keys_dir):
            os.makedirs(keys_dir)
        return keys_dir

    @staticmethod
    def _load_and_check_keys(priv_key_path: str,
                             password: str,
                             difficulty: int) -> Optional[Tuple[bytes, bytes]]:
        try:
            with open(priv_key_path, 'r') as f:
                keystore = f.read()
        except FileNotFoundError:
            return None
        keystore = json.loads(keystore)

        try:
            priv_key = decode_keystore_json(keystore, password)
        except ValueError:
            raise WrongPassword

        pub_key = privtopub(priv_key)

        if not KeysAuth.is_pubkey_difficult(pub_key, difficulty):
            raise Exception("Loaded key is not difficult enough")

        return priv_key, pub_key

    @staticmethod
    def _generate_keys(difficulty: int) -> Tuple[bytes, bytes]:
        from twisted.internet import reactor
        reactor_started = reactor.running
        logger.info("Generating new key pair")
        started = time.time()
        while True:
            priv_key = mk_privkey(str(get_random_float()))
            pub_key = privtopub(priv_key)
            if KeysAuth.is_pubkey_difficult(pub_key, difficulty):
                break

            # lets be responsive to reactor stop (eg. ^C hit by user)
            if reactor_started and not reactor.running:
                logger.warning("reactor stopped, aborting key generation ..")
                raise Exception("aborting key generation")

        logger.info("Keys generated in %.2fs", time.time() - started)
        return priv_key, pub_key

    @staticmethod
    def _save_private_key(key, key_path, password: str):
        # The default c parameter is quite large and makes the decryption take
        # more than 10 seconds which is annoying.
        ethereum.keys.PBKDF2_CONSTANTS["c"] = 1024
        keystore = make_keystore_json(
            key,
            password,
            kdf="pbkdf2",
            cipher="aes-128-ctr",
        )
        with open(key_path, 'w') as f:
            f.write(_serialize_keystore(keystore))

    @staticmethod
    def _count_max_hash(difficulty: int) -> int:
        return 2 << (256 - difficulty - 1)

    @staticmethod
    def is_pubkey_difficult(pub_key: Union[bytes, str],
                            difficulty: int) -> bool:
        if isinstance(pub_key, str):
            pub_key = decode_hex(pub_key)
        return sha2(pub_key) < KeysAuth._count_max_hash(difficulty)

    def is_difficult(self, difficulty: int) -> bool:
        return self.is_pubkey_difficult(self.public_key, difficulty)

    @staticmethod
    def get_difficulty(key_id: str) -> int:
        """
        Calculate given key difficulty.
        This is more expensive to calculate than is_difficult, so use
        the latter if possible.
        """
        return int(math.floor(256 - math.log2(sha2(decode_hex(key_id)))))

    def sign(self, data: bytes) -> bytes:
        """
        Sign given data with ECDSA;
        sha3 is used to shorten the data and speedup calculations.
        """
        return self.ecc.sign(data)

    def verify(self, sig: bytes, data: bytes,
               public_key: Optional[Union[bytes, str]] = None) -> bool:
        """
        Verify the validity of an ECDSA signature;
        sha3 is used to shorten the data and speedup calculations.

        :param sig: ECDSA signature
        :param data: expected data
        :param public_key: *Default: None* public key that should be used to
            verify signed data. Public key may be in digest (len == 64) or
            hexdigest (len == 128). If public key is None then default public
            key will be used.
        :return bool: verification result
        """

        try:
            if public_key is None:
                public_key = self.public_key
            elif len(public_key) > len(self.public_key):
                public_key = decode_hex(public_key)
            return ecdsa_verify(public_key, sig, data)
        except Exception as e:
            # Always log exceptions as repr, otherwise you'll see empty values
            # if excpetion args is empty. It happends because
            # str of BaseException returns str representation of args.
            # SEE:
            #    https://docs.python.org/3/library/exceptions.html#BaseException
            logger.error("Cannot verify signature: %r", e)
            logger.debug(
                ".verify(%r, %r, %r) failed",
                sig,
                data,
                public_key,
                exc_info=True,
            )
        return False
