"""GNR Compute Node"""

import os
import pickle
import click
import uuid
import logging.config

from twisted.internet import reactor

from golem.client import create_client
from golem.network.transport.tcpnetwork import TCPAddress
from golem.task.taskbase import Task

from examples.gnr.task.blenderrendertask import BlenderRenderTaskBuilder
from examples.gnr.task.luxrendertask import LuxRenderTaskBuilder
from examples.gnr.renderingenvironment import BlenderEnvironment, LuxRenderEnvironment

config_file = os.path.join(os.path.dirname(__file__), "logging.ini")
logging.config.fileConfig(config_file, disable_existing_loggers=False)

logger = logging.getLogger(__name__)


class Node(object):
    """ Simple Golem Node connecting console user interface with Client
    """
    default_environments = []

    def __init__(self):
        self.client = create_client()

    def initialize(self):
        self.client.start_network()
        self.load_environments(self.default_environments)

    def load_environments(self, environments):
        for env in environments:
            env.accept_task = True
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

    @staticmethod
    def run():
        reactor.run()


class GNRNode(Node):
    default_environments = [BlenderEnvironment(), LuxRenderEnvironment()]

    @staticmethod
    def _get_task_builder(task_def):
        #FIXME: temporary solution
        if task_def.main_scene_file.endswith('.blend'):
            return BlenderRenderTaskBuilder
        else:
            return LuxRenderTaskBuilder


def parse_peer(ctx, param, value):
    del ctx, param
    addresses = []
    for arg in value:
        try:
            addresses.append(TCPAddress.parse(arg))
        except ValueError:
            logger.warning("Wrong peer address {}. Address should be in format <ipv4_addr>:port "
                           "or [<ipv6_addr>]:port".format(arg))
    return addresses


def parse_task_file(ctx, param, value):
    del ctx, param
    tasks = []
    for task_file in value:
        task_def = pickle.loads(task_file.read())
        task_def.task_id = str(uuid.uuid4())
        tasks.append(task_def)
    return tasks


@click.command()
@click.option('--peer', '-p', multiple=True, callback=parse_peer,
              help="Connect with given peer: <ipv4_addr>:port or [<ipv6_addr>]:port")
@click.option('--task', '-t', multiple=True, type=click.File(lazy=True), callback=parse_task_file,
              help="Request task from file")
def start(peer, task):

    node = GNRNode()
    node.initialize()

    node.connect_with_peers(peer)
    node.add_tasks(task)

    node.run()


if __name__ == "__main__":
    start()
