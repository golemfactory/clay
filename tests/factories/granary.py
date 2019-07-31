import subprocess
from typing import Optional

import shlex

from eth_utils import encode_hex, decode_hex
from ethereum.utils import sha3

from golem_messages.cryptography import ECCx

_logging = False

def _log(*args):
    # Private log function since pytest.tearDown() does not print logger
    if _logging:
        print(*args)


GRANARY_EXECUTABLE_NAME = 'golem-granary'


class Account:
    def __init__(self, raw_key: bytes, ts: str):
        self.key = ECCx(raw_key)
        assert self.key.raw_privkey == raw_key
        self.raw_key = self.key.raw_privkey
        _log("Account created: " + str(self.raw_key))
        self.transaction_store = ts


class Granary:
    def __init__(self, hostname: Optional[str] = None):
        self.hostname = hostname

    def _cmd(self, *args):
        cmd = ['ssh', self.hostname] if self.hostname else []
        cmd.extend([GRANARY_EXECUTABLE_NAME, *args])
        return cmd

    def request_account(self) -> Optional[Account]:
        _log("Granary called, account requested")
        cmd = self._cmd('get_used_account')

        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True)
        _log('returncode:', completed.returncode, 'stderr:', completed.stderr)

        if not completed.stdout:
            print('stdout: EMPTY')
            return None

        _log('stdout:', completed.stdout)

        out_lines = completed.stdout.split('\n')
        raw_key = out_lines[0].strip()

        key = decode_hex(raw_key)
        _log('raw_key:', raw_key, 'key:', key)
        return Account(key, out_lines[1] or '{}')

    def return_account(self, account: Account):
        _log("Granary called, account returned. account=", account)

        key_pub_addr = encode_hex(sha3(account.key.raw_pubkey)[12:])

        ts = account.transaction_store or '{}'
        ts = shlex.quote(ts)

        cmd = self._cmd(
            'return_used_account',
            '-p', key_pub_addr,
            '-P', encode_hex(account.raw_key),
            '-t', ts
        )

        _log(cmd)
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True)
        _log(
            'returncode:', completed.returncode,
            'stdout:', completed.stdout,
            'stderr:', completed.stderr)
        return
