import logging
from typing import List, Optional, Callable

from twisted.internet import threads
from twisted.internet.defer import gatherResults, Deferred

from apps.appsmanager import AppsManager
from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.async import async_callback
from golem.core.keysauth import KeysAuth
from golem.docker.manager import DockerManager
from golem.network.transport.tcpnetwork_helpers import SocketAddress
from golem.rpc.mapping.rpcmethodnames import CORE_METHOD_MAP
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import object_method_map, Session

logger = logging.getLogger("app")


class Node(object):
    """ Simple Golem Node connecting console user interface with Client
    :type client golem.client.Client:
    """

    def __init__(self,  # noqa pylint: disable=too-many-arguments
                 datadir: str,
                 config_desc: ClientConfigDescriptor,
                 peers: Optional[List[SocketAddress]] = None,
                 transaction_system: bool = False,
                 use_monitor: bool = False,
                 use_docker_manager: bool = True,
                 start_geth: bool = False,
                 start_geth_port: Optional[int] = None,
                 geth_address: Optional[str] = None) -> None:

        # DO NOT MAKE THIS IMPORT GLOBAL
        # otherwise, reactor will install global signal handlers on import
        # and will prevent the IOCP / kqueue reactors from being installed.
        from twisted.internet import reactor

        self._reactor = reactor
        self._config_desc = config_desc
        self._datadir = datadir
        self._use_docker_manager = use_docker_manager

        self.rpc_router: Optional[CrossbarRouter] = None

        self._peers: List[SocketAddress] = peers or []

        self.client: Optional[Client] = None
        self._client_factory = lambda keys_auth: Client(
            datadir=datadir,
            config_desc=config_desc,
            keys_auth=keys_auth,
            transaction_system=transaction_system,
            use_docker_manager=use_docker_manager,
            use_monitor=use_monitor,
            start_geth=start_geth,
            start_geth_port=start_geth_port,
            geth_address=geth_address,
        )

    def start(self) -> None:
        try:
            rpc = self._start_rpc()
            keys = self._start_keys_auth()
            docker = self._start_docker()
            gatherResults([rpc, keys, docker], consumeErrors=True).addCallbacks(
                self._setup_client, self._error('rpc, keys or docker'))
            self._reactor.run()
        except Exception as exc:
            logger.exception("Application error: %r", exc)

    def _start_rpc(self) -> Deferred:
        self.rpc_router = rpc = CrossbarRouter(
            host=self._config_desc.rpc_address,
            port=self._config_desc.rpc_port,
            datadir=self._datadir,
        )
        deferred = rpc._start_node(rpc.options, self._reactor)
        self._reactor.addSystemEventTrigger("before", "shutdown", rpc.stop)
        return deferred

    def _start_keys_auth(self) -> Deferred:
        return threads.deferToThread(
            KeysAuth,
            datadir=self._datadir,
            difficulty=self._config_desc.key_difficulty
        )

    def _start_docker(self) -> Deferred:
        if not self._use_docker_manager:
            return None

        def start_docker():
            docker: DockerManager = DockerManager.install(self._config_desc)
            docker.check_environment()  # pylint: disable=no-member

        return threads.deferToThread(start_docker)

    def _setup_client(self, gathered_results: List) -> None:
        keys_auth = gathered_results[1]
        self.client = self._client_factory(keys_auth)
        self._reactor.addSystemEventTrigger("before", "shutdown",
                                            self.client.quit)

        methods = object_method_map(self.client, CORE_METHOD_MAP)
        rpc_session = Session(self.rpc_router.address,  # type: ignore
                              methods=methods)
        self.client.configure_rpc(rpc_session)
        rpc_session.connect().addCallbacks(
            async_callback(self._run), self._error('session connect'))

    def _run(self, *_) -> None:
        self._setup_apps()
        self.client.sync()

        try:
            self.client.start()
            for peer in self._peers:
                self.client.connect(peer)
        except SystemExit:
            self._reactor.callFromThread(self._reactor.stop)

    def _setup_apps(self) -> None:
        apps_manager = AppsManager()
        apps_manager.load_apps()

        for env in apps_manager.get_env_list():
            env.accept_tasks = True
            self.client.environments_manager.add_environment(env)

    def _error(self, msg: str) -> Callable:
        def log_error_and_stop_reactor(err):
            logger.error("Stopping because of %s error: %r", msg, err)
            self._reactor.callFromThread(self._reactor.stop)

        return log_error_and_stop_reactor
