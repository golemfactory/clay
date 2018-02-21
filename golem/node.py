import logging
from typing import List, Optional

from apps.appsmanager import AppsManager
from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.async import async_callback, AsyncRequest, async_run
from golem.core.keysauth import KeysAuth
from golem.docker.manager import DockerManager
from golem.network.transport.tcpnetwork_helpers import SocketAddress
from golem.report import StatusPublisher
from golem.rpc.mapping.rpcmethodnames import CORE_METHOD_MAP
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import object_method_map, Session, Publisher

logger = logging.getLogger("app")


def _error(msg: str):
    return lambda err: logger.error("%s error: %r", msg, err)


class Node(object):
    """ Simple Golem Node connecting console user interface with Client
    :type client golem.client.Client:
    """

    def __init__(self,  # noqa pylint: disable=too-many-arguments
                 datadir: str,
                 config_desc: ClientConfigDescriptor,
                 peers: List[SocketAddress] = [],
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
        self._config_desc: ClientConfigDescriptor = config_desc
        self._datadir: str = datadir
        self._use_docker_manager: bool = use_docker_manager

        self.keys_auth: Optional[KeysAuth] = None
        self._rpc_ready: bool = False
        self.rpc_router: Optional[CrossbarRouter] = None
        self.rpc_session: Optional[Session] = None

        self._peers: List[SocketAddress] = peers
        self._apps_manager: Optional[AppsManager] = None

        self.client: Optional[Client] = None
        self._client_factory = lambda: Client(
            datadir=datadir,
            config_desc=config_desc,
            keys_auth=self.keys_auth,
            transaction_system=transaction_system,
            use_docker_manager=use_docker_manager,
            use_monitor=use_monitor,
            start_geth=start_geth,
            start_geth_port=start_geth_port,
            geth_address=geth_address,
        )

        try:
            self._setup_rpc()
            self._setup_keys_auth()
            self._reactor.run()
        except Exception as exc:
            logger.exception("Application error: %r", exc)

    def _setup_rpc(self):
        self.rpc_router = CrossbarRouter(
            host=self._config_desc.rpc_address,
            port=self._config_desc.rpc_port,
            datadir=self._datadir,
        )
        self.rpc_router.start(self._reactor, self._rpc_router_ready,
                              _error('RPC'))
        self._reactor.addSystemEventTrigger(
            "before",
            "shutdown",
            self.rpc_router.stop,
        )

    def _rpc_router_ready(self, *_):
        logger.info("RPC ready")
        self._rpc_ready = True
        self._setup_session()
        if self.keys_auth:
            self._setup_client()
        else:
            logger.info("waiting for KeysAuth")

    def _setup_docker(self, *_):
        if self._use_docker_manager:
            logger.info("setting up docker")
            docker_manager = DockerManager.install(self._config_desc)
            docker_manager.check_environment()  # pylint: disable=no-member

    def _setup_session(self):
        self.rpc_session = Session(self.rpc_router.address)
        StatusPublisher.set_publisher(Publisher(self.rpc_session))
        # lets setup docker, especially when keys generation takes little longer
        self.rpc_session.connect().addCallback(
            async_callback(self._setup_docker), _error('RPC'))

    def _setup_keys_auth(self):
        async_constructor = AsyncRequest(
            KeysAuth, datadir=self._datadir,
            difficulty=self._config_desc.key_difficulty)

        async_run(async_constructor, self._key_auth_ready, _error('KeysAuth'))

    def _key_auth_ready(self, keys_auth: KeysAuth, *_):
        logger.info("KeysAuth ready")
        self.keys_auth = keys_auth
        if self._rpc_ready:
            self._setup_client()
        else:
            logger.info("waiting for RPC")

    def _setup_client(self):
        self.client = self._client_factory()
        self._reactor.addSystemEventTrigger("before", "shutdown",
                                            self.client.quit)

        self.rpc_session.methods = object_method_map(self.client,
                                                     CORE_METHOD_MAP)
        self._run()

    def _run(self, *_):
        self._setup_apps()
        self.client.sync()

        try:
            self.client.start()
            for peer in self._peers:
                self.client.connect(peer)
        except SystemExit:
            self._reactor.callFromThread(self._reactor.stop)

    def _setup_apps(self):
        self._apps_manager = AppsManager()
        self._apps_manager.load_apps()

        for env in self._apps_manager.get_env_list():
            env.accept_tasks = True
            self.client.environments_manager.add_environment(env)
