"""GNR Compute Node"""

import cPickle as pickle
import logging
import sys
import uuid

import click
import jsonpickle

from apps.blender.task.blenderrendertask import BlenderRenderTaskBuilder
from apps.blender.blenderenvironment import BlenderEnvironment
from apps.lux.task.luxrendertask import LuxRenderTaskBuilder
from apps.lux.luxenvironment import LuxRenderEnvironment

from golem.client import Client
from golem.network.transport.tcpnetwork import SocketAddress, AddressValueError
from golem.rpc.websockets import WebSocketRPCServerFactory
from golem.task.taskbase import Task


class Node(object):
    """ Simple Golem Node connecting console user interface with Client
    :type client golem.client.Client:
    """
    default_environments = []

    def __init__(self, datadir=None, transaction_system=False,
                 **config_overrides):

        self.client = Client(datadir=datadir,
                             transaction_system=transaction_system,
                             **config_overrides)

    def initialize(self):
        self.load_environments(self.default_environments)
        self.client.start()

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
                                                      self.client.datadir))
            self.client.enqueue_new_task(golem_task)

    def run(self, use_rpc=False):
        try:
            # Import reactor locally because it also installs it and GUI
            # requires Qt reactor version.
            from twisted.internet import reactor
            if use_rpc:
                config = self.client.config_desc
                reactor.callWhenRunning(self._start_rpc_server,
                                        config.rpc_address,
                                        config.rpc_port)
            reactor.run()
        except Exception as ex:
            logger = logging.getLogger("gnr.app")
            logger.error("Reactor error: {}".format(ex))
        finally:
            self.client.quit()
            sys.exit(0)

    def _start_rpc_server(self, host, port):
        rpc_server = WebSocketRPCServerFactory(interface=host, port=port)
        rpc_server.listen()
        self.client.set_rpc_server(rpc_server)

    @staticmethod
    def _get_task_builder(task_def):
        raise NotImplementedError


class GNRNode(Node):
    default_environments = [
        BlenderEnvironment(),
        LuxRenderEnvironment()
    ]

    @staticmethod
    def _get_task_builder(task_def):
        # FIXME: Add information about builder in task_def
        if task_def.main_scene_file.endswith('.blend'):
            return BlenderRenderTaskBuilder
        else:
            return LuxRenderTaskBuilder

    @staticmethod
    def parse_node_addr(ctx, param, value):
        del ctx, param
        if value:
            try:
                SocketAddress(value, 1)
                return value
            except AddressValueError as e:
                raise click.BadParameter(
                    "Invalid network address specified: {}".format(e.message))
        return ''

    @staticmethod
    def parse_peer(ctx, param, value):
        del ctx, param
        addresses = []
        for arg in value:
            try:
                addresses.append(SocketAddress.parse(arg))
            except AddressValueError as e:
                raise click.BadParameter(
                    "Invalid peer address specified: {}".format(e.message))
        return addresses

    @staticmethod
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
