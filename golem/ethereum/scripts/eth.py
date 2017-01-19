import jsonpickle as json
import logging
import os
from os import path

import click
import gevent
from ethereum import keys, abi
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms, int_to_big_endian, zpad

from golem.core.simpleenv import get_local_datadir
from golem.ethereum import Client
from golem.ethereum.contracts import BankOfDeposit, TestGNT
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
        data_dir = path.join(get_local_datadir("ethereum"))

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
        faucet_nonce = 0

    ctx.obj = O()


@app.group()
@click.pass_obj
def node(o):
    o.me = SimpleAccount(o.dir)
    print "MY ADDRESS", o.me.address.encode('hex')


@node.command('balance')
@click.pass_obj
def node_balance(o):
    print "BALANCE", o.eth.get_balance('0x' + o.me.address.encode('hex'))


@node.command()
@click.pass_obj
@click.argument('recipient')
@click.argument('value', type=int)
def direct(o, recipient, value):
    nonce = o.eth.get_transaction_count('0x' + o.me.address.encode('hex'))
    print "NONCE", nonce
    print "VALUE", value
    tx = Transaction(nonce, 1, 21000, to=recipient, value=value,
                     data='')
    tx.sign(o.me.priv)
    print o.eth.send(tx)
    gevent.sleep(1)  # FIXME: Wait for confirmed transaction receipt.


def encode_payment(to, value):
    value = long(value)
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
    print "multi payment"
    encp = []
    value = 0
    for p in payments:
        p = p.split(':')
        print "->", p[0], p[1]
        encp.append(encode_payment(p[0], p[1]))
        value += long(p[1])

    nonce = o.eth.get_transaction_count('0x' + o.me.address.encode('hex'))
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
    log_id = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
    my_addr = '0x' + zpad(o.me.address, 32).encode('hex')
    outgoing = o.eth.get_logs(from_block='earliest', topics=[log_id, my_addr])
    incomming = o.eth.get_logs(from_block='earliest', topics=[log_id, None, my_addr])

    balance = o.eth.get_balance('0x' + o.me.address.encode('hex'))
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
    faucet_addr = '0x' + Faucet.ADDR.encode('hex')
    o.faucet_nonce = o.eth.get_transaction_count(faucet_addr)
    print "NONCE", o.faucet_nonce
    if o.faucet_nonce == 0:  # Deploy Bank of Deposit contract
        tx = Transaction(o.faucet_nonce, 1, 3141592, to='', value=0,
                         data=BankOfDeposit.INIT_HEX.decode('hex'))
        tx.sign(Faucet.PRIVKEY)
        o.eth.send(tx)
        gevent.sleep(10)


@faucet.command('balance')
@click.pass_obj
def faucet_balance(o):
    print o.eth.get_balance('0x' + Faucet.ADDR.encode('hex'))


@faucet.command('testgnt')
@click.pass_obj
def faucet_testgnt(o):
    """ Deploy TestGNT contract."""
    tx = Transaction(o.faucet_nonce, 1, 3141592, to='', value=0,
                     data=TestGNT.INIT_HEX.decode('hex'))
    tx.sign(Faucet.PRIVKEY)
    o.eth.send(tx)
    print "TestGNT: {}".format(tx.creates.encode('hex'))
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
    print "Transaction sent:", r
    gevent.sleep(10)


if __name__ == '__main__':
    app()
