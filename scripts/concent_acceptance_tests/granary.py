import logging
from pathlib import Path
import random
import subprocess

import shlex

from eth_utils import encode_hex, decode_hex
from ethereum.utils import sha3

from golem_messages.cryptography import ECCx

logger = logging.getLogger(__name__)
# logger.setLevel(5)

class Granary:

    @staticmethod
    def request_account():
        logger.debug("Granary called, account requested")
        cmd = ['ssh', 'mwu-vps', '/home/ubuntu/.cargo/bin/golem-granary', 'get_used_account']


        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print('returncode:', completed.returncode)

        if completed.stderr:
            print('stderr:', completed.stderr)
        else:
            print('stderr: EMPTY')

        if completed.stdout:
            print('stdout:', completed.stdout)
            out_lines = completed.stdout.split('\n')
            raw_key = out_lines[0].strip()
            print('raw_key:', raw_key)
            key = decode_hex(raw_key)
            print('key:', key)
            return Account(key, out_lines[1] or None)
        else:
            print('stdout: EMPTY')
        return Account()

    @staticmethod
    def return_account(account):
        print("Granary called, account returned")
        print(account)
        print(account.raw_key)
        print(account.transaction_store)
        print(account.password)

        key_pub_addr = encode_hex(sha3(account.key.raw_pubkey)[12:])

        ts = account.transaction_store or '{}'
        ts = shlex.quote(ts)

        cmd = ['ssh', 'mwu-vps', '/home/ubuntu/.cargo/bin/golem-granary', 'return_used_account', '-p', key_pub_addr, '-P', encode_hex(account.raw_key), '-t', ts]

        print(cmd)
        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print('returncode:', completed.returncode)
        if completed.stdout:
            print('stdout:', completed.stdout)
        else:
            print('stdout: EMPTY')

        if completed.stderr:
            print('stderr:', completed.stderr)
        else:
            print('stderr: EMPTY')
        return

class Account:
    def __init__(self, raw_key = None, ts = None):
        self.key = ECCx(raw_key)
        if raw_key is not None:
            random.seed()
            assert(self.key.raw_privkey == raw_key)
        self.raw_key = self.key.raw_privkey
        logger.debug("Account created: " + str(self.raw_key))
        self.transaction_store = ts
