import json
import logging
import os
from os import path
from pprint import pprint

import appdirs
import click
import ethereum.slogging as slogging
import gevent
import pyethapp.config as konfig
from devp2p.peermanager import PeerManager
from devp2p.discovery import NodeDiscovery
from ethereum import blocks, keys, abi
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms, int_to_big_endian, big_endian_to_int
from pyethapp.accounts import Account, AccountsService
from pyethapp.app import EthApp
from pyethapp.db_service import DBService
from pyethapp.eth_service import ChainService
from pyethapp.pow_service import PoWService
from pyethapp.utils import merge_dict

from golem.ethereum import Client
from golem.ethereum.contracts import BankOfDeposit


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

slogging.configure(":info")

genesis_file = path.join(
    path.dirname(path.dirname(path.abspath(__file__))), 'genesis_golem.json')

FAUCET_PRIVKEY = "{:32}".format("Golem Faucet")
assert len(FAUCET_PRIVKEY) == 32
FAUCET_PUBKEY = "f1fbbeff7e9777a3a930f1e55a5486476845f799f7d603f71be7b00898df98f2dc2e81b854d2c774c3d266f1fa105d130d4a43bc58e700155c4565726ae6804e"  # noqa
FAUCET_ADDR = keys.privtoaddr(FAUCET_PRIVKEY)
SERVER_ENODE = "enode://" + FAUCET_PUBKEY + "@golemproject.org:30900"
BANK_ADDR = "cfdc7367e9ece2588afe4f530a9adaa69d5eaedb".decode('hex')

PROFILES = {
    'golem': {
        'eth': {
            'network_id': 9
        },
        'discovery': {
            'bootstrap_nodes': []
        },
    }
}

services = [DBService, AccountsService, NodeDiscovery, PeerManager,
            ChainService, PoWService]


def _build_config(data_dir, name):
    data_dir = path.join(data_dir, name)
    konfig.setup_data_dir(data_dir)
    config = konfig.load_config(data_dir)
    default_config = konfig.get_default_config([EthApp] + services)
    merge_dict(default_config, {'eth': {'block': blocks.default_config}})
    konfig.update_config_with_defaults(config, default_config)
    konfig.update_config_from_genesis_json(config, genesis_file)
    merge_dict(config, PROFILES['golem'])
    pprint(config)
    config['data_dir'] = data_dir
    config['discovery']['listen_port'] = 30301
    config['p2p']['listen_port'] = 30301
    return config


def _build_app(config):
    app = EthApp(config)
    for service in services:
        service.register_with_app(app)
    return app


@click.group()
@click.option('--data-dir')
@click.pass_context
def app(ctx, data_dir):
    if not data_dir:
        data_dir = path.join(appdirs.user_data_dir("golem"), "ethereum9")
    ctx.obj = data_dir

    logging.basicConfig(level=logging.DEBUG)
    geth = Client()
    while not geth.get_peer_count():
        gevent.sleep(1)
    for i in range(10):
        gevent.sleep(1)
        geth.is_syncing()
    while geth.is_syncing():
        gevent.sleep(1)


@app.command()
@click.pass_obj
def server(data_dir):
    config = _build_config(data_dir, 'server')
    config['accounts']['privkeys_hex'] = [FAUCET_PRIVKEY.encode('hex')]
    config['node']['privkey_hex'] = FAUCET_PRIVKEY.encode('hex')
    config['discovery']['listen_port'] = 30300
    config['p2p']['listen_port'] = 30300
    config['p2p']['min_peers'] = 0  # Do not try to connect to boostrap nodes.
    config['pow']['activated'] = True
    config['pow']['mine_empty_blocks'] = False
    config['pow']['cpu_pct'] = 5
    # config['pow']['coinbase_hex'] = FAUCET_ADDR.encode('hex')
    app = _build_app(config)
    app.start()


@app.group()
@click.option('--name', default='node')
@click.option('bootstrap_node', '-b', required=False)
@click.pass_context
def node(ctx, name, bootstrap_node):
    data_dir = ctx.obj

    config = _build_config(data_dir, name)
    if bootstrap_node:
        config['discovery']['bootstrap_nodes'].append(bootstrap_node)
    else:
        config['discovery']['bootstrap_nodes'].append(SERVER_ENODE)
    app = _build_app(config)
    ctx.obj = app


@node.command()
@click.pass_obj
@click.argument('recipient')
@click.argument('value', type=int)
def direct(app, recipient, value):
    geth = Client()
    me = SimpleAccount(path.join(app.config['data_dir']))

    print "MY ADDRESS", me.address.encode('hex')
    nonce = geth.get_transaction_count(me.address.encode('hex'))
    print "NONCE", nonce
    print "VALUE", value
    tx = Transaction(nonce, 1, 21000, to=recipient, value=value,
                     data='')
    tx.sign(me.priv)
    print geth.send(tx)


def encode_payment(to, value):
    value = long(value)
    assert value < 2**96
    value = int_to_big_endian(value)
    assert type(value) is str
    if len(value) < 12:
        value = '\0' * (12 - len(value)) + value
    assert len(value) == 12
    to = normalize_address(to)
    assert len(to) == 20
    mix = value + to
    assert len(mix) == 32
    return mix


@node.command()
@click.pass_obj
@click.argument('payments', nargs=-1, required=True)
def multi(app, payments):
    print "multi payment"
    data = ''
    encp = []
    value = 0
    for p in payments:
        p = p.split(':')
        print "->", p[0], p[1]
        encp.append(encode_payment(p[0], p[1]))
        value += long(p[1])

    geth = Client()
    me = SimpleAccount(path.join(app.config['data_dir']))
    print "MY ADDRESS", me.address.encode('hex')
    nonce = geth.get_transaction_count(me.address.encode('hex'))

    translator = abi.ContractTranslator(BankOfDeposit.ABI)
    data = translator.encode('transfer', [encp])
    print "DATA: ", data.encode('hex')

    gas = 21000 + len(encp) * 30000
    tx = Transaction(nonce, 1, gas, to=BANK_ADDR, value=value, data=data)
    tx.sign(me.priv)
    print geth.send(tx)


@node.command()
@click.pass_obj
def history(app):
    geth = Client()
    me = SimpleAccount(path.join(app.config['data_dir']))
    id = hex(100389287136786176327247604509743168900146139575972864366142685224231313322991L)
    outgoing = geth.get_logs(topics=[id, me.address.encode('hex')])
    print outgoing
    incomming = geth.get_logs(topics=[id, None, me.address.encode('hex')])
    print incomming

    print "MY ADDRESS", me.address.encode('hex')
    balance = geth.get_balance(me.address.encode('hex'))
    print "BALANCE", balance

    print "OUTGOING"
    for p in outgoing:
        print "[{}] -> {} {}".format(int(p['blockNumber'], 16), p['topics'][2][-40:], int(p['data'], 16))

    print "INCOMING"
    for p in incomming:
        print "[{}] -> {} {}".format(p['blockNumber'], p['topics'][1][-40:], p['data'])


@app.group()
@click.pass_context
def faucet(ctx):
    logging.basicConfig(level=logging.DEBUG)
    geth = Client()
    while not geth.get_peer_count():
        gevent.sleep(1)
    for i in range(10):
        gevent.sleep(1)
        geth.is_syncing()
    while geth.is_syncing():
        gevent.sleep(1)

    data_dir = ctx.obj  # FIXME: set geth's data dir
    nonce = geth.get_transaction_count(FAUCET_ADDR.encode('hex'))

    print "NONCE", nonce
    if nonce == 0:  # Deploy Bank of Deposit contract
        tx = Transaction(nonce, 1, 3141592, to='', value=0,
                         data=BankOfDeposit.INIT_HEX.decode('hex'))
        tx.sign(FAUCET_PRIVKEY)
        geth.send(tx)
        addr = tx.creates
        assert addr == "cfdc7367e9ece2588afe4f530a9adaa69d5eaedb".decode('hex')
        print "ADDR", addr.encode('hex')
    ctx.obj = app


@faucet.command('balance')
@click.pass_obj
def faucet_balance(app):
    print Client().get_balance(FAUCET_ADDR.encode('hex'))


@faucet.command('send')
@click.argument('to')
@click.argument('value', default=1)
@click.pass_obj
def faucet_send(app, to, value):
    geth = Client()
    value = int(value * denoms.ether)
    nonce = geth.get_transaction_count(FAUCET_ADDR.encode('hex'))
    to = normalize_address(to)
    tx = Transaction(nonce, 1, 21000, to, value, '')
    tx.sign(FAUCET_PRIVKEY)
    r = geth.send(tx)
    print "Transaction sent:", r
    gevent.sleep(10)


if __name__ == '__main__':
    app()
