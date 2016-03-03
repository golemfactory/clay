"""GNR Compute Node"""

import os
import cPickle as pickle
import jsonpickle
import click
import uuid
import sys
import logging.config

from twisted.internet import reactor

from golem.client import create_client
from golem.network.transport.tcpnetwork import TCPAddress, AddressValueError
from golem.core.common import get_golem_path
from golem.task.docker.client import disable_docker
from golem.task.taskbase import Task

from gnr.task.blenderrendertask import BlenderRenderTaskBuilder
from gnr.task.luxrendertask import LuxRenderTaskBuilder
from gnr.renderingenvironment import BlenderEnvironment, LuxRenderEnvironment
from gnr.docker_environments import BlenderDockerEnvironment


def config_logging():
    """Config logger"""
    config_file = os.path.normpath(os.path.join(get_golem_path(), "gnr/logging.ini"))
    logging.config.fileConfig(config_file, disable_existing_loggers=False)


config_logging()
logger = logging.getLogger(__name__)


class Node(object):
    """ Simple Golem Node connecting console user interface with Client
    :type client golem.client.Client:
    """
    default_environments = []

    def __init__(self, **config_overrides):
        self.client = create_client(**config_overrides)

    def initialize(self):
        self.client.start_network()
        self.load_environments(self.default_environments)

    def load_environments(self, environments):
        for env in environments:
            env.accept_tasks = True
            self.client.environments_manager.add_environment(env)

    def connect_with_peers(self, peers):
        for peer in peers:
            self.client.connect(peer)

    def add_tasks(self, tasks):
        for task_def in tasks:
            task_builder = self._get_task_builder(task_def)
            golem_task = Task.build_task(task_builder(self.client.get_node_name(), task_def,
                                                      self.client.get_root_path()))
            self.client.enqueue_new_task(golem_task)

    def run(self):
        try:
            reactor.run()
        finally:
            self.client.quit()
            sys.exit(0)


class GNRNode(Node):
    default_environments = (
        [BlenderEnvironment(), LuxRenderEnvironment()] +
        [] if disable_docker() else [BlenderDockerEnvironment()]
    )

    @staticmethod
    def _get_task_builder(task_def):
        #FIXME: temporary solution
        if task_def.main_scene_file.endswith('.blend'):
            return BlenderRenderTaskBuilder
        else:
            return LuxRenderTaskBuilder


def parse_node_addr(ctx, param, value):
    del ctx, param
    if value:
        try:
            TCPAddress(value, 1)
            return value
        except AddressValueError as e:
            raise click.BadParameter(
                "Invalid network address specified: {}".format(e.message))
    return ''


def parse_peer(ctx, param, value):
    del ctx, param
    addresses = []
    for arg in value:
        try:
            addresses.append(TCPAddress.parse(arg))
        except AddressValueError as e:
            raise click.BadParameter(
                "Invalid peer address specified: {}".format(e.message))
    return addresses


def parse_task_file(ctx, param, value):
    del ctx, param
    tasks = []
    for task_file in value:
        with open(task_file, 'r') as f:
            if f.name.endswith('.json'):
                try:
                    task_def = jsonpickle.decode(f.read())
                except ValueError as e:
                    raise click.BadParameter(
                        "Invalid task json file: {}".format(e.message))
            else:
                task_def = pickle.loads(f.read())
        task_def.task_id = str(uuid.uuid4())
        tasks.append(task_def)
    return tasks


@click.group()
def node_cli():
    pass


@node_cli.command()
@click.option('--node-address', '-a', multiple=False, type=click.STRING,
              callback=parse_node_addr,
              help="Network address to use for this node")
@click.option('--peer', '-p', multiple=True, callback=parse_peer,
              help="Connect with given peer: <ipv4_addr>:<port> or [<ipv6_addr>]:<port>")
@click.option('--task', '-t', multiple=True, type=click.Path(exists=True),
              callback=parse_task_file,
              help="Request task from file")
def start(node_address, peer, task, **extra_args):
    del extra_args

    node = GNRNode(node_address=node_address)
    node.initialize()

    node.connect_with_peers(peer)
    node.add_tasks(task)

    node.run()


if __name__ == "__main__":
    start()
