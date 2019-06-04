import random
import subprocess
from typing import Optional

import shlex

from eth_utils import encode_hex, decode_hex
from ethereum.utils import sha3

from golem_messages.cryptography import ECCx

_logging = False


class Account:
    def __init__(self, raw_key, ts):
        self.key = ECCx(raw_key)
        random.seed()
        assert self.key.raw_privkey == raw_key
        self.raw_key = self.key.raw_privkey
        if _logging:
            print("Account created: " + str(self.raw_key))
        self.transaction_store = ts


class Granary:
    def __init__(self, hostname):
        self.hostname = hostname

    def request_account(self) -> Optional[Account]:
        if _logging:
            print("Granary called, account requested")
        cmd = ['ssh', self.hostname, 'golem-granary', 'get_used_account']

        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True)
        if _logging:
            print('returncode:', completed.returncode)

        if _logging:
            if completed.stderr:
                print('stderr:', completed.stderr)
            else:
                print('stderr: EMPTY')

        if completed.stdout:
            if _logging:
                print('stdout:', completed.stdout)
            out_lines = completed.stdout.split('\n')
            raw_key = out_lines[0].strip()

            if _logging:
                print('raw_key:', raw_key)
            key = decode_hex(raw_key)
            if _logging:
                print('key:', key)
            return Account(key, out_lines[1] or None)
        elif _logging:
            print('stdout: EMPTY')
        return None

    def return_account(self, account):
        if _logging:
            print("Granary called, account returned")
            print(account)
            print(account.raw_key)
            print(account.transaction_store)

        key_pub_addr = encode_hex(sha3(account.key.raw_pubkey)[12:])

        ts = account.transaction_store or '{}'
        ts = shlex.quote(ts)

        cmd = ['ssh', self.hostname, 'golem-granary', 'return_used_account',
               '-p', key_pub_addr, '-P', encode_hex(account.raw_key), '-t', ts]

        if _logging:
            print(cmd)
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True)
        if _logging:
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
