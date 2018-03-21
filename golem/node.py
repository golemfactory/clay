import logging
import time
from typing import List, Optional, Callable

from twisted.internet import threads
from twisted.internet.defer import gatherResults, Deferred

from apps.appsmanager import AppsManager
from golem.appconfig import AppConfig
from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.deferred import chain_function
from golem.core.keysauth import KeysAuth, WrongPassword
from golem.core.async import async_run, AsyncRequest
from golem.core.variables import PRIVATE_KEY
from golem.database import Database
from golem.docker.manager import DockerManager
from golem.model import DB_MODELS, db, DB_FIELDS, GenericKeyValue
from golem.network.transport.tcpnetwork_helpers import SocketAddress
from golem.report import StatusPublisher, Component, Stage
from golem.rpc.mapping.rpcmethodnames import CORE_METHOD_MAP
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import object_method_map, Session, Publisher

logger = logging.getLogger("app")


# pylint: disable=too-many-instance-attributes
class Node(object):  # pylint: disable=too-few-public-methods
    """ Simple Golem Node connecting console user interface with Client
    :type client golem.client.Client:
    """
    TERMS_ACCEPTED_KEY = 'terms_of_use_accepted'

    def __init__(self,  # noqa pylint: disable=too-many-arguments
                 datadir: str,
                 app_config: AppConfig,
                 config_desc: ClientConfigDescriptor,
                 peers: Optional[List[SocketAddress]] = None,
                 use_monitor: bool = False,
                 use_concent: bool = False,
                 mainnet: bool = False,
                 use_docker_manager: bool = True,
                 start_geth: bool = False,
                 start_geth_port: Optional[int] = None,
                 geth_address: Optional[str] = None,
                 password: Optional[str] = None) -> None:

        # DO NOT MAKE THIS IMPORT GLOBAL
        # otherwise, reactor will install global signal handlers on import
        # and will prevent the IOCP / kqueue reactors from being installed.
        from twisted.internet import reactor

        self._reactor = reactor
        self._config_desc = config_desc
        self._datadir = datadir
        self._use_docker_manager = use_docker_manager

        self._keys_auth: Optional[KeysAuth] = None

        self.rpc_router: Optional[CrossbarRouter] = None
        self.rpc_session: Optional[Session] = None
        self._rpc_publisher: Optional[Publisher] = None

        self._peers: List[SocketAddress] = peers or []

        # Initialize database
        self._db = Database(
            db, fields=DB_FIELDS, models=DB_MODELS, db_dir=datadir)

        self.client: Optional[Client] = None
        self._client_factory = lambda keys_auth: Client(
            datadir=datadir,
            app_config=app_config,
            config_desc=config_desc,
            keys_auth=keys_auth,
            database=self._db,
            mainnet=mainnet,
            use_docker_manager=use_docker_manager,
            use_monitor=use_monitor,
            use_concent=use_concent,
            start_geth=start_geth,
            start_geth_port=start_geth_port,
            geth_address=geth_address,
        )

        if password is not None:
            if not self.set_password(password):
                raise Exception("Password incorrect")

    def start(self) -> None:

        try:
            rpc = self._start_rpc()

            def on_rpc_ready() -> Deferred:
                terms = self._check_terms()
                keys = self._start_keys_auth()
                docker = self._start_docker()
                return gatherResults([terms, keys, docker], consumeErrors=True)
            chain_function(rpc, on_rpc_ready).addCallbacks(
                self._setup_client,
                self._error('keys or docker'),
            ).addErrback(self._error('setup client'))
            self._reactor.run()
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Application error: %r", exc)

    def set_password(self, password: str) -> bool:
        logger.info("Got password")

        try:
            self._keys_auth = KeysAuth(
                datadir=self._datadir,
                private_key_name=PRIVATE_KEY,
                password=password,
                difficulty=self._config_desc.key_difficulty,
            )
        except WrongPassword:
            logger.info("Password incorrect")
            return False
        return True

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
        deferred = self.rpc_session.connect()

        def set_publisher(*_):
            self._rpc_publisher = Publisher(self.rpc_session)
            StatusPublisher.set_publisher(self._rpc_publisher)

        return deferred.addCallbacks(set_publisher, self._error('rpc session'))

    def are_terms_accepted(self):
        return GenericKeyValue.select()\
            .where(GenericKeyValue.key == self.TERMS_ACCEPTED_KEY)\
            .count() > 0

    def accept_terms(self):
        GenericKeyValue.get_or_create(key=self.TERMS_ACCEPTED_KEY)

    def _check_terms(self) -> Optional[Deferred]:
        if not self.rpc_session:
            self._error("RPC session is not available")
            return None

        self.rpc_session.register_methods([
            (self.are_terms_accepted, 'golem.terms'),
            (self.accept_terms, 'golem.terms.accept'),
        ])

        def wait_for_terms():
            while not self.are_terms_accepted() and self._reactor.running:
                logger.info(
                    'Terms of use must be accepted before using Golem. '
                    'Run `golemcli terms show` to display the terms '
                    'and `golemcli terms accept` to accept them.')
                time.sleep(5)

        return threads.deferToThread(wait_for_terms)

    def _start_keys_auth(self) -> Optional[Deferred]:
        if not self.rpc_session:
            self._error("RPC session is not available")
            return None

        def create_keysauth():
            # If keys_auth already exists it means we used command line flag
            # and don't need to inform client about required password
            if self._keys_auth is not None:
                return

            if KeysAuth.key_exists(self._datadir, PRIVATE_KEY):
                event = 'get_password'
                logger.info("Waiting for password to unlock the account")
            else:
                event = 'new_password'
                logger.info("New account, need to create new password")

            while self._keys_auth is None and self._reactor.running:
                StatusPublisher.publish(Component.client, event, Stage.pre)
                time.sleep(5)

            StatusPublisher.publish(Component.client, event, Stage.post)

        self.rpc_session.register_methods([
            (self.set_password, 'golem.password.set')
        ])

        return threads.deferToThread(create_keysauth)

    def _start_docker(self) -> Optional[Deferred]:
        if not self._use_docker_manager:
            return None

        def start_docker():
            DockerManager.install(self._config_desc).check_environment()  # noqa pylint: disable=no-member

        return threads.deferToThread(start_docker)

    def _setup_client(self, *_) -> None:
        if not self.rpc_session:
            self._error("RPC session is not available")
            return

        if not self._keys_auth:
            self._error("KeysAuth is not available")
            return

        self.client = self._client_factory(self._keys_auth)
        self._reactor.addSystemEventTrigger("before", "shutdown",
                                            self.client.quit)

        methods = object_method_map(self.client, CORE_METHOD_MAP)
        self.rpc_session.register_methods(methods)
        self.client.set_rpc_publisher(self._rpc_publisher)

        async_run(AsyncRequest(self._run),
                  error=self._error('Cannot start the client'))

    def _run(self, *_) -> None:
        if not self.client:
            self._error("Client object is not available")
            return

        self._setup_apps()
        self.client.sync()

        try:
            self.client.start()
            for peer in self._peers:
                self.client.connect(peer)
        except SystemExit:
            self._reactor.callFromThread(self._reactor.stop)

    def _setup_apps(self) -> None:
        if not self.client:
            self._error("Client object is not available")
            return

        apps_manager = AppsManager()
        apps_manager.load_apps()

        for env in apps_manager.get_env_list():
            env.accept_tasks = True
            self.client.environments_manager.add_environment(env)

    def _error(self, msg: str) -> Callable:
        def log_error_and_stop_reactor(err):
            if self._reactor.running:
                logger.error("Stopping because of %s error: %s", msg, err)
                self._reactor.callFromThread(self._reactor.stop)

        return log_error_and_stop_reactor
