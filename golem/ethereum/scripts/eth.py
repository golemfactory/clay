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

from golem.ethereum.contracts import BankOfDeposit

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
    accounts = app.services.accounts
    print accounts.keystore_dir
    if len(accounts) == 0:
        me = Account.new('')
        me.path = accounts.propose_path(me.address)
        accounts.add_account(me)
    app.start()
    ctx.obj = app


@node.command()
@click.pass_obj
@click.argument('recipient')
@click.argument('value', type=int)
def direct(app, recipient, value):
    me = app.services.accounts[0]
    print "MY ADDRESS", me.address.encode('hex')
    svc = app.services.chain
    head = svc.chain.head
    nonce = head.get_nonce(me.address)
    print "NONCE", nonce
    print "VALUE", value
    tx = Transaction(nonce, 1, 21000, to=recipient.decode('hex'), value=value,
                     data='')
    me.unlock('')
    assert me.privkey
    tx.sign(me.privkey)
    svc.add_transaction(tx)


def encode_payment(to, value):
    value = long(value)
    assert value < 2**96
    value = int_to_big_endian(value)
    assert type(value) is str
    if len(value) < 12:
        value = '\0' * (12 - len(value)) + value
    assert len(value) == 12
    to = to.decode('hex')
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

    me = app.services.accounts[0]
    print "MY ADDRESS", me.address.encode('hex')
    svc = app.services.chain
    head = svc.chain.head
    nonce = head.get_nonce(me.address)

    translator = abi.ContractTranslator(BankOfDeposit.ABI)
    data = translator.encode('transfer', [encp])
    print "DATA: ", data.encode('hex')

    gas = 21000 + len(encp) * 30000
    tx = Transaction(nonce, 1, gas, to=BANK_ADDR, value=value, data=data)
    me.unlock('')
    assert me.privkey
    tx.sign(me.privkey)
    svc.add_transaction(tx)


@node.command()
@click.pass_obj
def history(app):
    while not app.services.peermanager.num_peers():
        print "waiting for connection..."
        gevent.sleep(1)
    gevent.sleep(1)
    while app.services.chain.is_syncing:
        print "syncing..."
        gevent.sleep(1)

    me = app.services.accounts[0]
    print "MY ADDRESS", me.address.encode('hex')
    svc = app.services.chain
    head = svc.chain.head
    nonce = head.get_nonce(me.address)
    print "NONCE", nonce
    balance = head.get_balance(me.address)
    print "BALANCE", balance

    incomming = []
    outgoing = []
    b = head
    while b:
        txs = b.get_transactions()
        for i, tx in enumerate(txs):
            if tx.to == me.address:
                incomming.append((tx.sender, tx.value, True, b.number, i))
            elif tx.to == BANK_ADDR:
                receipt = b.get_receipt(i)
                for log in receipt.logs:
                    to = int_to_big_endian(log.topics[2])
                    if to == me.address:
                        sender = int_to_big_endian(log.topics[1])
                        value = big_endian_to_int(log.data)
                        incomming.append((sender, value, False, b.number, i))

            if tx.sender == me.address:
                if tx.to == BANK_ADDR:
                    receipt = b.get_receipt(i)
                    for log in receipt.logs:
                        to = int_to_big_endian(log.topics[2])
                        value = big_endian_to_int(log.data)
                        outgoing.append((to, value, False, b.number, i))
                else:
                    outgoing.append((tx.to, tx.value, True, b.number, i))
        b = b.get_parent() if not b.is_genesis() else None

    print "OUTGOING"
    for p in outgoing:
        print "[{}]".format(p[3]), "->", p[0].encode('hex'), p[1], "(direct)" if p[2] else "(indirect)"

    print "INCOMING"
    for p in incomming:
        print "[{}]".format(p[3]), "<-", p[0].encode('hex'), p[1], "(direct)" if p[2] else "(indirect)"


@app.group()
@click.pass_context
def faucet(ctx):
    data_dir = ctx.obj
    config = _build_config(data_dir, 'faucet')
    config['discovery']['bootstrap_nodes'].append(SERVER_ENODE)
    app = _build_app(config)
    app.start()
    while not app.services.peermanager.num_peers():
        print "waiting for connection..."
        gevent.sleep(1)
    gevent.sleep(1)
    while app.services.chain.is_syncing:
        print "syncing..."
        gevent.sleep(1)

    svc = app.services.chain
    head = svc.chain.head
    nonce = head.get_nonce(FAUCET_ADDR)
    print "NONCE", nonce
    if nonce == 0:  # Deploy Bank of Deposit contract
        tx = Transaction(nonce, 1, 3141592, to='', value=0,
                         data=BankOfDeposit.INIT_HEX.decode('hex'))
        tx.sign(FAUCET_PRIVKEY)
        svc.add_transaction(tx)
        addr = tx.creates
        assert addr == "cfdc7367e9ece2588afe4f530a9adaa69d5eaedb".decode('hex')
        print "ADDR", addr.encode('hex')
    ctx.obj = app


@faucet.command('balance')
@click.pass_obj
def faucet_balance(app):
    gevent.sleep(2)
    while app.services.chain.is_syncing:
        gevent.sleep(1)
    print app.services.chain.chain.head.get_balance(FAUCET_ADDR)
    # app.stop()


@faucet.command('send')
@click.argument('to')
@click.argument('value', default=1)
@click.pass_obj
def faucet_send(app, to, value):
    svc = app.services.chain
    chain = svc.chain
    value = int(value * denoms.ether)
    nonce = chain.head_candidate.get_nonce(FAUCET_ADDR)
    to = normalize_address(to)
    tx = Transaction(nonce, 1, 21000, to, value, '')
    tx.sign(FAUCET_PRIVKEY)
    svc.add_transaction(tx)
    print "Transaction added."
    # app.stop()


if __name__ == '__main__':
    app()
