"""GNR Compute Node"""

import os
import pickle
import click
import uuid
import logging.config

from golem.client import create_client
from golem.network.transport.tcpnetwork import TCPAddress
from examples.gnr.nodelogic import Logic
from twisted.internet import reactor

config_file = os.path.join(os.path.dirname(__file__), "logging.ini")
logging.config.fileConfig(config_file, disable_existing_loggers=False)

logger = logging.getLogger(__name__)


def parse_peer(ctx, param, value):
    addresses = []
    for arg in value:
        try:
            if arg.startswith("["):
                addr = __parse_ipv6(arg)
            else:
                addr = __parse_ipv4(arg)
            addresses.append(addr)
        except ValueError:
            logger.warning("Wrong peer address {}. Address should be in format <ipv4_addr>:port "
                           "or [<ipv6_addr>]:port".format(arg))
    return addresses


def parse_task_file(ctx, param, value):
    tasks = []
    for task_file in value:
        task_def = pickle.loads(task_file.read())
        task_def.task_id = "{}".format(uuid.uuid4())
        tasks.append(task_def)
    return tasks


@click.command()
@click.option('--peer', '-p', multiple=True, callback=parse_peer,
              help="Connect with given peer: <ipv4_addr>:port or [<ipv6_addr>]:port")
@click.option('--task', '-t', multiple=True, type=click.File(lazy=True), callback=parse_task_file,
              help="Request task from file")
def start_node(peer, task):
    client = create_client()
    client.start_network()
    logic = Logic(client)

    logic.load_environments()
    logic.connect_with_peers(peer)
    logic.add_tasks(task)

    run_node()


def run_node():
    reactor.run()


def __parse_ipv6(addr_arg):
    print addr_arg
    host, port = addr_arg.split("]")
    host = host[1:]
    port = int(port[1:])
    return TCPAddress(host, port)


def __parse_ipv4(addr_arg):
    host, port = addr_arg.split(":")
    port = int(port)
    return TCPAddress(host, port)

if __name__ == "__main__":
    start_node()
