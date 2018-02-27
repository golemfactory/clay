import logging
from typing import List, Optional, Callable

from twisted.internet import threads
from twisted.internet.defer import gatherResults, Deferred

from apps.appsmanager import AppsManager
from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.deferred import chain_function
from golem.core.keysauth import KeysAuth
from golem.core.async import async_run, AsyncRequest
from golem.docker.manager import DockerManager
from golem.network.transport.tcpnetwork_helpers import SocketAddress
from golem.report import StatusPublisher
from golem.rpc.mapping.rpcmethodnames import CORE_METHOD_MAP
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import object_method_map, Session, Publisher

logger = logging.getLogger("app")


class Node(object):  # pylint: disable=too-few-public-methods
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
        # pylint: disable=too-many-instance-attributes

        # DO NOT MAKE THIS IMPORT GLOBAL
        # otherwise, reactor will install global signal handlers on import
        # and will prevent the IOCP / kqueue reactors from being installed.
        from twisted.internet import reactor

        self._reactor = reactor
        self._config_desc = config_desc
        self._datadir = datadir
        self._use_docker_manager = use_docker_manager

        self.rpc_router: Optional[CrossbarRouter] = None
        self.rpc_session: Optional[Session] = None

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
        def _start(_):
            publisher = Publisher(self.rpc_session)
            StatusPublisher.set_publisher(publisher)

            keys = self._start_keys_auth()
            docker = self._start_docker()
            gatherResults([keys, docker], consumeErrors=True).addCallbacks(
                self._setup_client,
                self._error('keys or docker')
            )

        try:
            self._start_rpc().addCallbacks(_start, self._error('rpc'))
            self._reactor.run()
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Application error: %r", exc)

    def _start_rpc(self) -> Deferred:
        self.rpc_router = rpc = CrossbarRouter(
            host=self._config_desc.rpc_address,
            port=self._config_desc.rpc_port,
            datadir=self._datadir,
        )
        self._reactor.addSystemEventTrigger("before", "shutdown", rpc.stop)

        # pylint: disable=protected-access
        deferred = rpc._start_node(rpc.options, self._reactor)
        return chain_function(deferred, self._start_session)

    def _start_session(self) -> Deferred:
        self.rpc_session = Session(self.rpc_router.address)  # type: ignore
        return self.rpc_session.connect()

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
        keys_auth = gathered_results[0]
        self.client = self._client_factory(keys_auth)
        self._reactor.addSystemEventTrigger("before", "shutdown",
                                            self.client.quit)

        methods = object_method_map(self.client, CORE_METHOD_MAP)
        self.rpc_session.methods = methods
        self.rpc_session.register_methods(methods)
        self.client.configure_rpc(self.rpc_session)

        async_run(AsyncRequest(self._run))

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
