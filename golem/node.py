"""Compute Node"""

import click
import gevent

from apps.appsmanager import AppsManager
from golem.client import Client
from golem.core.async import async_callback
from golem.core.common import to_unicode
from golem.network.transport.tcpnetwork import SocketAddress, AddressValueError
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.session import object_method_map, Session


class Node(object):
    """ Simple Golem Node connecting console user interface with Client
    :type client golem.client.Client:
    """

    def __init__(self, datadir=None, peers=None, transaction_system=False,
                 use_monitor=False, use_docker_machine_manager=True,
                 geth_port=None, **config_overrides):

        self.client = Client(
            datadir=datadir,
            transaction_system=transaction_system,
            use_docker_machine_manager=use_docker_machine_manager,
            use_monitor=use_monitor,
            geth_port=geth_port,
            **config_overrides
        )
        self.client.connect()

        self.rpc_router = None
        self.rpc_session = None

        self._peers = peers or []
        self._apps_manager = None

        import logging
        self.logger = logging.getLogger("app")

    def run(self, use_rpc=False):
        from twisted.internet import reactor

        try:
            if use_rpc:
                self._setup_rpc()
                self._start_rpc_router()
            else:
                self._run()

            reactor.run()
            gevent.get_hub().join()
        except Exception as exc:
            self.logger.error("Application error: {}".format(exc))
        finally:
            self.client.quit()

    def _run(self, *_):
        if self.client.use_docker_machine_manager:
            self._setup_docker()
        self._setup_apps()

        for peer in self._peers:
            self.client.connect(peer)
        self.client.sync()

        try:
            self.client.start()
            for peer in self._peers:
                self.client.connect(peer)
        except SystemExit:
            from twisted.internet import reactor
            reactor.callFromThread(reactor.stop)

    def _setup_rpc(self):
        from golem.rpc.router import CrossbarRouter

        config = self.client.config_desc
        methods = object_method_map(self.client, CORE_METHOD_MAP)

        self.rpc_router = CrossbarRouter(host=config.rpc_address,
                                         port=int(config.rpc_port),
                                         datadir=self.client.datadir)
        self.rpc_session = Session(self.rpc_router.address,
                                   methods=methods)

        self.client.configure_rpc(self.rpc_session)

    def _setup_docker(self):
        from golem.docker.manager import DockerManager

        docker_manager = DockerManager.install(self.client.config_desc)
        docker_manager.check_environment()

    def _setup_apps(self):
        self._apps_manager = AppsManager()
        self._apps_manager.load_apps()

        for env in self._apps_manager.get_env_list():
            env.accept_tasks = True
            self.client.environments_manager.add_environment(env)

    def _start_rpc_router(self):
        from twisted.internet import reactor

        reactor.addSystemEventTrigger("before", "shutdown",
                                      self.client.quit)
        reactor.addSystemEventTrigger("before", "shutdown",
                                      self.rpc_router.stop)

        self.rpc_router.start(reactor, self._rpc_router_ready, self._rpc_error)

    def _rpc_router_ready(self, *_):
        self.rpc_session.connect().addCallbacks(async_callback(self._run),
                                                self._rpc_error)

    def _rpc_error(self, err):
        self.logger.error("RPC error: {}".format(err))


class OptNode(Node):

    @staticmethod
    def parse_node_addr(ctx, param, value):
        del ctx, param
        if value:
            try:
                SocketAddress(value, 1)
                return value
            except AddressValueError as e:
                raise click.BadParameter(
                    "Invalid network address specified: {}".format(e))
        return ''

    @staticmethod
    def parse_rpc_address(ctx, param, value):
        del ctx, param
        value = to_unicode(value)
        if value:
            try:
                return SocketAddress.parse(value)
            except AddressValueError as e:
                raise click.BadParameter(
                    "Invalid RPC address specified: {}".format(e))

    @staticmethod
    def parse_peer(ctx, param, value):
        del ctx, param
        addresses = []
        for arg in value:
            try:
                node_id, sock_addr = arg.split('@', 1)
                addresses.append([SocketAddress.parse(sock_addr), node_id])
            except (AddressValueError, ValueError) as e:
                raise click.BadParameter(
                    "Invalid peer address specified: {}".format(e))
        return addresses
