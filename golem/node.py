"""Compute Node"""

import sys
import uuid

import click
import jsonpickle as json

from apps.appsmanager import AppsManager
from golem.client import Client
from golem.core.common import is_windows
from golem.network.transport.tcpnetwork import SocketAddress, AddressValueError
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.session import object_method_map, Session
from golem.task.taskbase import Task


class Node(object):
    """ Simple Golem Node connecting console user interface with Client
    :type client golem.client.Client:
    """

    def __init__(self, datadir=None, transaction_system=False,
                 **config_overrides):

        self.default_environments = []
        self.client = Client(datadir=datadir,
                             transaction_system=transaction_system,
                             **config_overrides)

        self.rpc_router = None
        self.rpc_session = None

        import logging
        self.logger = logging.getLogger("app")

    def initialize(self):
        self.load_environments(self.default_environments)
        self.client.sync()
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
            from twisted.internet import reactor

            if use_rpc:
                config = self.client.config_desc
                reactor.callWhenRunning(self._start_rpc_server,
                                        config.rpc_address,
                                        int(config.rpc_port))
            reactor.run()
        except Exception as ex:
            self.logger.error("Reactor error: {}".format(ex))
        finally:
            self.client.quit()
            sys.exit(0)

    def _start_rpc_server(self, host, port):
        from twisted.internet import reactor
        from golem.rpc.router import CrossbarRouter
        self.rpc_router = CrossbarRouter(host=host, port=port,
                                         datadir=self.client.datadir)
        reactor.addSystemEventTrigger("before", "shutdown",
                                      self.rpc_router.stop)
        self.rpc_router.start(reactor, self._router_ready, self._rpc_error)

    def _router_ready(self, *_):
        methods = object_method_map(self.client, CORE_METHOD_MAP)
        self.rpc_session = Session(self.rpc_router.address, methods=methods)
        self.client.configure_rpc(self.rpc_session)
        self.rpc_session.connect().addErrback(self._rpc_error)

    def _rpc_error(self, err):
        self.logger.error("RPC error: {}".format(err))

    def _get_task_builder(self, task_def):
        raise NotImplementedError


class OptNode(Node):
    def __init__(self, datadir=None, transaction_system=False, **config_overrides):
        super(OptNode, self).__init__(datadir, transaction_system, **config_overrides)
        self.apps_manager = AppsManager()
        self.apps_manager.load_apps()
        self.default_environments = self.apps_manager.get_env_list()

    def _get_task_builder(self, task_def):
        return self.apps_manager.apps[task_def.task_type].builder

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
    def parse_rpc_address(ctx, param, value):
        del ctx, param
        if value:
            try:
                return SocketAddress.parse(value)
            except AddressValueError as e:
                raise click.BadParameter(
                    "Invalid RPC address specified: {}".format(e.message))

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
                try:
                    task_def = json.loads(f.read())
                except ValueError as e:
                    raise click.BadParameter(
                        "Invalid task json file: {}".format(e.message))
            task_def.task_id = str(uuid.uuid4())
            tasks.append(task_def)
        return tasks
