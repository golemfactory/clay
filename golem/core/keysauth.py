import json
import logging
import math
import os
import sys
import time
from hashlib import sha256
from typing import Optional, Tuple, Union

from eth_keyfile import create_keyfile_json, decode_keyfile_json
from eth_utils import encode_hex, decode_hex
from golem_messages.cryptography import ECCx, mk_privkey, ecdsa_verify, \
    privtopub
from golem_messages.utils import pubkey_to_address

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


class WrongPassword(Exception):
    pass


class KeysAuth:
    """
    Elliptical curves cryptographic authorization manager. Generates
    private and public keys based on ECC (curve secp256k1). Private key is
    stored in file. When this file not exist or is broken new key is generated.
    """
    KEYS_SUBDIR = 'keys'

    _private_key: bytes = b''
    public_key: bytes = b''
    key_id: str = ""
    ecc: ECCx = None

    def __init__(
            self,
            datadir: str,
            private_key_name: str,
            password: str,
    ) -> None:
        """
        Create new ECC keys authorization manager, load or create keys.

        :param datadir where to store files
        :param private_key_name: name of the file containing private key
        :param password: user password to protect private key
        """

        prv, pub = KeysAuth._load_or_generate_keys(
            datadir, private_key_name, password)

        self._private_key = prv
        self.ecc = ECCx(prv)
        self.public_key = pub
        self.key_id = encode_hex(pub)[2:]
        self.eth_addr = pubkey_to_address(pub)

    @staticmethod
    def key_exists(datadir: str, private_key_name: str) -> bool:
        keys_dir = KeysAuth._get_or_create_keys_dir(datadir)
        priv_key_path = os.path.join(keys_dir, private_key_name)
        return os.path.isfile(priv_key_path)

    @staticmethod
    def _load_or_generate_keys(
            datadir: str,
            filename: str,
            password: str,
    ) -> Tuple[bytes, bytes]:
        keys_dir = KeysAuth._get_or_create_keys_dir(datadir)
        priv_key_path = os.path.join(keys_dir, filename)

        loaded_keys = KeysAuth._load_and_check_keys(
            priv_key_path,
            password,
        )

        if loaded_keys:
            logger.debug('Existing keys loaded')
            priv_key, pub_key = loaded_keys
        else:
            logger.debug('No keys found, generating new one')
            priv_key, pub_key = KeysAuth._generate_keys()
            logger.debug('Generation completed, saving keys')
            KeysAuth._save_private_key(priv_key, priv_key_path, password)
            logger.debug('Keys stored succesfully')

        return priv_key, pub_key

    @staticmethod
    def _get_or_create_keys_dir(datadir: str) -> str:
        keys_dir = os.path.join(datadir, KeysAuth.KEYS_SUBDIR)
        if not os.path.isdir(keys_dir):
            os.makedirs(keys_dir)
        return keys_dir

    @staticmethod
    def _load_and_check_keys(
            priv_key_path: str,
            password: str,
    ) -> Optional[Tuple[bytes, bytes]]:
        try:
            with open(priv_key_path, 'r') as f:
                keystore = f.read()
        except FileNotFoundError:
            return None
        keystore = json.loads(keystore)

        try:
            priv_key = decode_keyfile_json(keystore, password.encode('utf-8'))
        except ValueError:
            raise WrongPassword

        pub_key = privtopub(priv_key)

        return priv_key, pub_key

    @staticmethod
    def _generate_keys() -> Tuple[bytes, bytes]:
        logger.info("Generating new key pair")
        priv_key = mk_privkey(str(get_random_float()))
        pub_key = privtopub(priv_key)
        return priv_key, pub_key

    @staticmethod
    def _save_private_key(key, key_path, password: str):
        keystore = create_keyfile_json(
            key,
            password.encode('utf-8'),
            iterations=1024,
        )
        with open(key_path, 'w') as f:
            f.write(json.dumps(keystore))

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
