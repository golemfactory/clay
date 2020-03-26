#!/usr/bin/env python3

from getpass import getpass
import os.path
import time

import appdirs
from golem_messages import cryptography

import golem
from golem import model


def ask(prompt, default):
    answer = input(f"{prompt} [{default}]: ")
    return answer or default


def main():
    datadir = ask(
        'datadir',
        os.path.join(appdirs.user_data_dir('golem'), 'default'),
    )
    port = ask('RPC port', '61000')
    cli_invocation = f"golemcli -d {datadir} -p {port} debug rpc "
    timestamp = int(time.time())
    broadcast_type = model.Broadcast.TYPE(
        ask('broadcast type', model.Broadcast.TYPE.Version.value),
    )
    print('selected', broadcast_type)
    data = ask('data', golem.__version__).encode('ascii')
    print(
        cli_invocation +
        f"broadcast.hash {timestamp} {broadcast_type.value} {data.hex()}",
    )
    hash_ = bytes.fromhex(input('hash hex: '))
    private_key = bytes.fromhex(getpass('Private key (hex): '))
    signature = cryptography.ecdsa_sign(private_key, hash_)
    print(
        cli_invocation +
        f"broadcast.push {timestamp} {broadcast_type.value} {data.hex()}"
        f" {signature.hex()}",
    )
    print(
        cli_invocation +
        "broadcast.list",
    )


if __name__ == '__main__':
    main()
