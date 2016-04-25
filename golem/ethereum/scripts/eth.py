import json
import logging
import os
from os import path

import click
import gevent
from ethereum import keys, abi
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms, int_to_big_endian, zpad

from golem.core.simpleenv import _get_local_datadir
from golem.ethereum import Client
from golem.ethereum.contracts import BankOfDeposit
from golem.ethereum.node import Faucet


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


SERVER_ENODE = "enode://" + Faucet.PUBKEY.encode('hex') + "@golemproject.org:30900"
BANK_ADDR = "cfdc7367e9ece2588afe4f530a9adaa69d5eaedb".decode('hex')


@click.group()
@click.pass_context
@click.option('--data-dir')
@click.option('--name')
def app(ctx, data_dir, name):
    if not data_dir:
        data_dir = path.join(_get_local_datadir("ethereum"))

    logging.basicConfig(level=logging.DEBUG)
    geth = Client(data_dir)
    while not geth.get_peer_count():
        print "Waiting for peers..."
        gevent.sleep(1)
    gevent.sleep(10)  # geth's downloader starts after 10s
    while geth.is_syncing():
        gevent.sleep(1)

    class O:
        dir = data_dir
        eth = geth
        me = None

    ctx.obj = O()


@app.group()
@click.pass_obj
def node(o):
    o.me = SimpleAccount(o.dir)
    print "MY ADDRESS", o.me.address.encode('hex')


@node.command()
@click.pass_obj
@click.argument('recipient')
@click.argument('value', type=int)
def direct(o, recipient, value):
    nonce = o.eth.get_transaction_count(o.me.address.encode('hex'))
    print "NONCE", nonce
    print "VALUE", value
    tx = Transaction(nonce, 1, 21000, to=recipient, value=value,
                     data='')
    tx.sign(o.me.priv)
    print o.eth.send(tx)
    gevent.sleep(1)  # FIXME: Wait for confirmed transaction receipt.


def encode_payment(to, value):
    value = long(value)
    assert value < 2**96
    value = zpad(int_to_big_endian(value), 12)
    assert type(value) is str
    assert len(value) == 12
    to = normalize_address(to)
    assert len(to) == 20
    mix = value + to
    assert len(mix) == 32
    return mix


@node.command()
@click.pass_obj
@click.argument('payments', nargs=-1, required=True)
def multi(o, payments):
    print "multi payment"
    data = ''
    encp = []
    value = 0
    for p in payments:
        p = p.split(':')
        print "->", p[0], p[1]
        encp.append(encode_payment(p[0], p[1]))
        value += long(p[1])

    nonce = o.eth.get_transaction_count(o.me.address.encode('hex'))
    translator = abi.ContractTranslator(BankOfDeposit.ABI)
    data = translator.encode('transfer', [encp])
    print "DATA: ", data.encode('hex')

    gas = 21000 + len(encp) * 30000
    tx = Transaction(nonce, 1, gas, to=BANK_ADDR, value=value, data=data)
    tx.sign(o.me.priv)
    print o.eth.send(tx)


@node.command()
@click.pass_obj
def history(o):
    id = hex(100389287136786176327247604509743168900146139575972864366142685224231313322991L)
    outgoing = o.eth.get_logs(from_block='earliest', topics=[id, o.me.address.encode('hex')])
    incomming = o.eth.get_logs(from_block='earliest', topics=[id, None, o.me.address.encode('hex')])

    balance = o.eth.get_balance(o.me.address.encode('hex'))
    print "BALANCE", balance

    print "OUTGOING"
    for p in outgoing:
        print "[{}] -> {} {}".format(int(p['blockNumber'], 16), p['topics'][2][-40:], int(p['data'], 16))

    print "INCOMING"
    for p in incomming:
        print "[{}] -> {} {}".format(p['blockNumber'], p['topics'][1][-40:], p['data'])


@app.group()
@click.pass_obj
def faucet(o):
    nonce = o.eth.get_transaction_count(Faucet.ADDR.encode('hex'))
    print "NONCE", nonce
    if nonce == 0:  # Deploy Bank of Deposit contract
        tx = Transaction(nonce, 1, 3141592, to='', value=0,
                         data=BankOfDeposit.INIT_HEX.decode('hex'))
        tx.sign(Faucet.PRIVKEY)
        o.eth.send(tx)
        addr = tx.creates
        assert addr == "cfdc7367e9ece2588afe4f530a9adaa69d5eaedb".decode('hex')
        print "ADDR", addr.encode('hex')


@faucet.command('balance')
@click.pass_obj
def faucet_balance(o):
    print o.eth.get_balance(Faucet.ADDR.encode('hex'))


@faucet.command('send')
@click.pass_obj
@click.argument('to')
@click.argument('value', default=1)
def faucet_send(o, to, value):
    value = int(value * denoms.ether)
    nonce = o.eth.get_transaction_count(Faucet.ADDR.encode('hex'))
    to = normalize_address(to)
    tx = Transaction(nonce, 1, 21000, to, value, '')
    tx.sign(Faucet.PRIVKEY)
    r = o.eth.send(tx)
    print "Transaction sent:", r
    gevent.sleep(10)


if __name__ == '__main__':
    app()
