from os import path
from pprint import pprint

import appdirs
import click
import ethereum.slogging as slogging
import gevent
import pyethapp.config as konfig
from devp2p.peermanager import PeerManager
from devp2p.discovery import NodeDiscovery
from ethereum import blocks, keys
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms
from pyethapp.accounts import AccountsService
from pyethapp.app import EthApp
from pyethapp.db_service import DBService
from pyethapp.eth_service import ChainService
from pyethapp.pow_service import PoWService
from pyethapp.utils import merge_dict

slogging.configure(":info")

genesis_file = path.join(
    path.dirname(path.abspath(__file__)), 'genesis_golem.json')

FAUCET_PRIVKEY = "{:32}".format("Golem Faucet")
assert len(FAUCET_PRIVKEY) == 32
FAUCET_PUBKEY = "f1fbbeff7e9777a3a930f1e55a5486476845f799f7d603f71be7b00898df98f2dc2e81b854d2c774c3d266f1fa105d130d4a43bc58e700155c4565726ae6804e"  # noqa
FAUCET_ADDR = keys.privtoaddr(FAUCET_PRIVKEY)
SERVER_ENODE = "enode://" + FAUCET_PUBKEY + "@golemproject.org:30300"

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
        data_dir = path.join(appdirs.user_data_dir("Golem"), "eth")
    ctx.obj = data_dir


@app.command()
@click.pass_obj
def server(data_dir):
    config = _build_config(data_dir, 'server')
    config['accounts']['privkeys_hex'][0] = FAUCET_PRIVKEY.encode('hex')
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


@app.command()
@click.option('--name', default='node')
@click.argument('bootstrap_node', required=False)
@click.pass_obj
def run(data_dir, name, bootstrap_node):
    config = _build_config(data_dir, name)
    if bootstrap_node:
        config['discovery']['bootstrap_nodes'].append(bootstrap_node)
    else:
        config['discovery']['bootstrap_nodes'].append(SERVER_ENODE)
    _build_app(config).start()


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
    ctx.obj = app


@faucet.command('balance')
@click.pass_obj
def faucet_balance(app):
    slogging.configure(":error")
    gevent.sleep(2)
    while app.services.chain.is_syncing:
        gevent.sleep(1)
    print app.services.chain.chain.head.get_balance(FAUCET_ADDR)
    app.stop()


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
    # app.stop()


if __name__ == '__main__':
    app()
