#!/usr/bin/env python

import json
import logging
import os
import sys
from os import path

import click
import gevent
from ethereum import keys, abi
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms, int_to_big_endian, zpad

from golem.core.simpleenv import get_local_datadir
from golem.ethereum import Client
from golem.ethereum.contracts import BankOfDeposit, TestGNT
from golem.utils import encode_hex, decode_hex
from golem_messages.cryptography import privtopub


class Faucet(object):
    PRIVKEY = "{:32}".format("Golem Faucet").encode()
    PUBKEY = privtopub(PRIVKEY)
    ADDR = keys.privtoaddr(PRIVKEY)

    @staticmethod
    def gimme_money(ethnode, addr, value):
        nonce = ethnode.get_transaction_count(encode_hex(Faucet.ADDR))
        addr = normalize_address(addr)
        tx = Transaction(nonce, 1, 21000, addr, value, '')
        tx.sign(Faucet.PRIVKEY)
        h = ethnode.send(tx)
        h = decode_hex(h[2:])
        return h


class SimpleAccount:
    def __init__(self, datadir):
        keyfile = path.join(datadir, 'ethkey.json')
        if path.exists(keyfile):
            data = json.load(open(keyfile, 'r'))
            self.priv = keys.decode_keystore_json(data, "FIXME: password!")
        else:
            self.priv = os.urandom(32)
            data = keys.make_keystore_json(self.priv, "FIXME: password!")
            json.dump(data, open(keyfile, 'w'))
        self.address = keys.privtoaddr(self.priv)


SERVER_ENODE = "enode://" + encode_hex(Faucet.PUBKEY)[2:] + \
               "@golemproject.org:30900"
BANK_ADDR = decode_hex("cfdc7367e9ece2588afe4f530a9adaa69d5eaedb")


@click.group()
@click.pass_context
@click.option('--data-dir')
@click.option('--name')
def app(ctx, data_dir, name):
    if not data_dir:
        data_dir = path.join(get_local_datadir("ethereum"))

    logging.basicConfig(level=logging.DEBUG)
    geth = Client()
    while not geth.get_peer_count():
        print("Waiting for peers...")
        gevent.sleep(1)
    gevent.sleep(10)  # geth's downloader starts after 10s
    while geth.is_syncing():
        gevent.sleep(1)

    class O:
        dir = data_dir
        eth = geth
        me = None
        faucet_nonce = 0

    ctx.obj = O()


@app.group()
@click.pass_obj
def node(o):
    o.me = SimpleAccount(o.dir)
    print("MY ADDRESS", o.me.address.encode('hex'))


@node.command('balance')
@click.pass_obj
def node_balance(o):
    print("BALANCE", o.eth.get_balance(encode_hex(o.me.address)))


@node.command()
@click.pass_obj
@click.argument('recipient')
@click.argument('value', type=int)
def direct(o, recipient, value):
    nonce = o.eth.get_transaction_count(encode_hex(o.me.address))
    print("NONCE", nonce)
    print("VALUE", value)
    tx = Transaction(nonce, 1, 21000, to=recipient, value=value,
                     data='')
    tx.sign(o.me.priv)
    print(o.eth.send(tx))
    gevent.sleep(1)  # FIXME: Wait for confirmed transaction receipt.


def encode_payment(to, value):
    value = int(value)
    max_value = 2**96
    if value >= max_value:
        raise ValueError("value: {}, should be less than: {}".format(value, max_value))
    value = zpad(int_to_big_endian(value), 12)
    if len(value) != 12:
        raise ValueError("Incorrect 'value' length: {}, should be 12".format(len(value)))
    to = normalize_address(to)
    if len(to) != 20:
        raise ValueError("Incorrect 'to' length: {}, should be 20".format(len(to)))
    mix = value + to
    return mix


@node.command()
@click.pass_obj
@click.argument('payments', nargs=-1, required=True)
def multi(o, payments):
    print("multi payment")
    encp = []
    value = 0
    for p in payments:
        p = p.split(':')
        print("->", p[0], p[1])
        encp.append(encode_payment(p[0], p[1]))
        value += int(p[1])

    nonce = o.eth.get_transaction_count(encode_hex(o.me.address))
    translator = abi.ContractTranslator(BankOfDeposit.ABI)
    data = translator.encode('transfer', [encp])
    print("DATA: ", data.encode('hex'))

    gas = 21000 + len(encp) * 30000
    tx = Transaction(nonce, 1, gas, to=BANK_ADDR, value=value, data=data)
    tx.sign(o.me.priv)
    print(o.eth.send(tx))


@node.command()
@click.pass_obj
def history(o):
    log_id = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
    my_addr = '0x' + zpad(o.me.address, 32).encode('hex')

    def get_logs_step(**kwargs):
        """Iteratively dive deeper into blockchain
        until result of eth.get_logs(**kwargs) is found.
        """
        # Iteration starts from newest block
        blocknumber = o.eth.web3.eth.blockNumber
        # Every iteration will go that much deeper
        step = 2**8
        result = []
        while not (result or blocknumber <= 0):
            if (blocknumber / step) % 2**4 == 0:
                # Show progress to avoid user frustration
                sys.stdout.write('.')
            if (blocknumber / step) % 2**10 == 0:
                # Show further progress information
                # to increase user satisfaction
                sys.stdout.write(str(blocknumber))
            result = o.eth.get_logs(
                from_block=max(blocknumber - step, 0),
                to_block=blocknumber,
                **kwargs
            )
            sys.stdout.flush()
            blocknumber -= step
        sys.stdout.write('#\n')
        return result
    # Get incoming transactions/contract logs
    outgoing = get_logs_step(topics=[log_id, my_addr])
    # Get outgoing transactions/contract logs
    incoming = get_logs_step(topics=[log_id, None, my_addr])

    import web3.utils.compat.compat_stdlib
    try:
        balance = o.eth.get_balance('0x' + o.me.address.encode('hex'))
    except web3.utils.compat.compat_stdlib.Timeout:
        balance = "<timeout>"
    print("BALANCE", balance)

    for label, l in \
            (
                ("OUTGOING", outgoing),
                ("INCOMING", incoming),
            ):
        print(label)
        for p in l:
            print("[{}] -> {} {}".format(
                p['blockNumber'],
                p['topics'][2][-40:],
                int(p['data'], 16)
            ))


@app.group()
@click.pass_obj
def faucet(o):
    faucet_addr = encode_hex(Faucet.ADDR)[2:]
    o.faucet_nonce = o.eth.get_transaction_count(faucet_addr)
    print("NONCE", o.faucet_nonce)
    if o.faucet_nonce == 0:  # Deploy Bank of Deposit contract
        tx = Transaction(o.faucet_nonce, 1, 3141592, to='', value=0,
                         data=BankOfDeposit.INIT_HEX.decode('hex'))
        tx.sign(Faucet.PRIVKEY)
        o.eth.send(tx)
        gevent.sleep(10)


@faucet.command('balance')
@click.pass_obj
def faucet_balance(o):
    print(o.eth.get_balance('0x' + Faucet.ADDR.encode('hex')))


@faucet.command('testgnt')
@click.pass_obj
def faucet_testgnt(o):
    """ Deploy TestGNT contract."""
    tx = Transaction(o.faucet_nonce, 1, 3141592, to='', value=0,
                     data=TestGNT.INIT_HEX.decode('hex'))
    tx.sign(Faucet.PRIVKEY)
    o.eth.send(tx)
    print("TestGNT: {}".format(tx.creates.encode('hex')))
    gevent.sleep(10)


@faucet.command('send')
@click.pass_obj
@click.argument('to')
@click.argument('value', default=1)
def faucet_send(o, to, value):
    value = int(value * denoms.ether)
    to = normalize_address(to)
    tx = Transaction(o.faucet_nonce, 1, 21000, to, value, '')
    tx.sign(Faucet.PRIVKEY)
    r = o.eth.send(tx)
    print("Transaction sent:", r)
    gevent.sleep(10)


if __name__ == '__main__':
    app()
