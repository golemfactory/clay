import logging
from pathlib import Path
import random

from eth_utils import encode_hex
from ethereum.utils import sha3

from golem_messages.cryptography import ECCx

BASE_DIR = '/Users/mwu-gol/tmp/granary/'
KEY_FILE_NAME = 'key'
TS_FILE_NAME = 'ts'
PASS_FILE_NAME = 'pass'
LOCK_FILE_NAME = 'lock'

logger = logging.getLogger(__name__)
logger.setLevel(5)

class Granary:

    @staticmethod
    def request_account():
        def _load_if_exists(path):
            if path.exists():
                return path.read_text()
            return None
        # TODO: read from granary service
        logger.debug("Granary called, account requested")
        walk_folder = Path(BASE_DIR)
        # Ensure it exists
        walk_folder.mkdir(exist_ok=True)
        for key_folder in walk_folder.iterdir():

            logger.debug("Checking key: " + str(key_folder))
            if not key_folder.is_dir():
                logger.debug('Not a dir, skipping')
                continue

            lock_file = key_folder / LOCK_FILE_NAME
            if lock_file.exists():
                logger.debug('This key is locked, skipping')
                continue
            logger.info('Unlocked key found, locking...')
            try:
                lock_file.touch()
                key = (key_folder / KEY_FILE_NAME).read_bytes()
                ts = _load_if_exists(key_folder / TS_FILE_NAME)
                password = _load_if_exists(key_folder / PASS_FILE_NAME)
                logger.info('Key locked and read, returning Account')
                return Account(key, ts, password)
            except:
                logger.info('Failed to load account from granary')
                continue
        logger.debug("Granary done, giving new account")
        return Account()

    @staticmethod
    def return_account(account):
        # TODO: read from granary service
        print("Granary called, account returned")
        print(account)
        print(account.raw_key)
        print(account.transaction_store)
        print(account.password)

        key_pub_addr = encode_hex(sha3(account.key.raw_pubkey)[12:])
        key_folder = Path(BASE_DIR, key_pub_addr)
        existing_key = key_folder.exists()
        key_folder.mkdir(exist_ok=True)
        print("Storing key in folder: " + str(key_folder))
        (key_folder / KEY_FILE_NAME).write_bytes(account.raw_key)
        if account.transaction_store is not None:
            (key_folder / TS_FILE_NAME).write_text(account.transaction_store)
        if account.password is not None:
            (key_folder / PASS_FILE_NAME).write_text(account.password)
        if existing_key:
            print("Removing lock file")
            (key_folder / LOCK_FILE_NAME).unlink()
        print("DONE")

class Account:
    def __init__(self, raw_key = None, ts = None, password = None):
        self.key = ECCx(raw_key)
        if raw_key is not None:
            random.seed()
            assert(self.key.raw_privkey == raw_key)
        self.raw_key = self.key.raw_privkey
        logger.debug("Account created: " + str(self.raw_key))
        self.transaction_store = ts
        self.password = password
