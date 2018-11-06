from enum import IntEnum
import functools
import logging
import time
from typing import (
    Any,
    Callable,
    cast,
    List,
    Optional,
    TypeVar,
)

from pathlib import Path
from twisted.internet import threads
from twisted.internet.defer import gatherResults, Deferred
from twisted.python.failure import Failure

from apps.appsmanager import AppsManager
import golem
from golem.appconfig import AppConfig
from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.config.active import IS_MAINNET, EthereumConfig
from golem.core.deferred import chain_function
from golem.core.keysauth import KeysAuth, WrongPassword
from golem.core import golem_async
from golem.core.variables import PRIVATE_KEY
from golem.database import Database
from golem.docker.manager import DockerManager
from golem.ethereum.transactionsystem import TransactionSystem
from golem.model import DB_MODELS, db, DB_FIELDS
from golem.network.transport.tcpnetwork_helpers import SocketAddress
from golem.report import StatusPublisher, Component, Stage
from golem.rpc import utils as rpc_utils
from golem.rpc.mapping import rpceventnames
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import (
    Publisher,
    Session,
)
from golem.terms import TermsOfUse

F = TypeVar('F', bound=Callable[..., Any])
logger = logging.getLogger(__name__)


def require_rpc_session() -> Callable:
    def wrapped(f: F) -> F:
        @functools.wraps(f)
        def curry(self: 'Node', *args, **kwargs):
            if self.rpc_session is None:
                self._error("RPC session is not available")  # noqa pylint: disable=protected-access
                return None
            return f(self, *args, **kwargs)
        return cast(F, curry)
    return wrapped


class ShutdownResponse(IntEnum):
    quit = 0
    off = 1
    on = 2


# pylint: disable=too-many-instance-attributes
class Node(object):
    """ Simple Golem Node connecting console user interface with Client
    :type client golem.client.Client:
    """

    def __init__(self,  # noqa pylint: disable=too-many-arguments
                 datadir: str,
                 app_config: AppConfig,
                 config_desc: ClientConfigDescriptor,
                 # SEE golem.core.variables.CONCENT_CHOICES
                 concent_variant: dict,
                 peers: Optional[List[SocketAddress]] = None,
                 use_monitor: bool = None,
                 use_talkback: bool = None,
                 use_docker_manager: bool = True,
                 geth_address: Optional[str] = None,
                 password: Optional[str] = None
                ) -> None:

        # DO NOT MAKE THIS IMPORT GLOBAL
        # otherwise, reactor will install global signal handlers on import
        # and will prevent the IOCP / kqueue reactors from being installed.
        from twisted.internet import reactor

        self._reactor = reactor
        self._app_config = app_config
        self._config_desc = config_desc
        self._datadir = datadir
        self._use_docker_manager = use_docker_manager
        self._docker_manager: Optional[DockerManager] = None

        self._use_monitor = config_desc.enable_monitor \
            if use_monitor is None else use_monitor
        self._use_talkback = config_desc.enable_talkback \
            if use_talkback is None else use_talkback

        self._keys_auth: Optional[KeysAuth] = None
        self._ets = TransactionSystem(
            Path(datadir) / 'transaction_system',
            EthereumConfig,
        )
        self._ets.backwards_compatibility_tx_storage(Path(datadir))

        self.rpc_router: Optional[CrossbarRouter] = None
        self.rpc_session: Optional[Session] = None
        self._rpc_publisher: Optional[Publisher] = None

        self._peers: List[SocketAddress] = peers or []

        # Initialize database
        self._db = Database(
            db, fields=DB_FIELDS, models=DB_MODELS, db_dir=datadir)

        self.client: Optional[Client] = None

        self.apps_manager = AppsManager()

        self._client_factory = lambda keys_auth: Client(
            datadir=datadir,
            app_config=app_config,
            config_desc=config_desc,
            keys_auth=keys_auth,
            database=self._db,
            transaction_system=self._ets,
            use_docker_manager=use_docker_manager,
            use_monitor=self._use_monitor,
            concent_variant=concent_variant,
            geth_address=geth_address,
            apps_manager=self.apps_manager,
            task_finished_cb=self._try_shutdown
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
        except Exception:  # pylint: disable=broad-except
            logger.exception("Application error")

    @rpc_utils.expose('ui.quit')
    def quit(self) -> None:

        def _quit():
            docker_manager = self._docker_manager
            if docker_manager:
                docker_manager.quit()

            reactor = self._reactor
            if reactor.running:
                reactor.callFromThread(reactor.stop)

        # Call in a separate thread and return early
        from threading import Thread
        Thread(target=_quit).start()

    @rpc_utils.expose('golem.password.set')
    def set_password(self, password: str) -> bool:
        logger.info("Got password")

        try:
            self._keys_auth = KeysAuth(
                datadir=self._datadir,
                private_key_name=PRIVATE_KEY,
                password=password,
                difficulty=self._config_desc.key_difficulty,
            )
            # When Golem is ready to use different Ethereum account for
            # payments and identity this should be called only when
            # idendity was not just created above for the first time.
            self._ets.backwards_compatibility_privkey(
                self._keys_auth._private_key,  # noqa pylint: disable=protected-access
                password,
            )
            self._ets.set_password(password)
        except WrongPassword:
            logger.info("Password incorrect")
            return False
        return True

    @rpc_utils.expose('golem.password.key_exists')
    def key_exists(self) -> bool:
        return KeysAuth.key_exists(self._datadir, PRIVATE_KEY)

    @rpc_utils.expose('golem.password.unlocked')
    def is_account_unlocked(self) -> bool:
        return self._keys_auth is not None

    @rpc_utils.expose('golem.mainnet')
    @classmethod
    def is_mainnet(cls) -> bool:
        return IS_MAINNET

    def _start_rpc(self) -> Deferred:
        self.rpc_router = rpc = CrossbarRouter(
            host=self._config_desc.rpc_address,
            port=self._config_desc.rpc_port,
            datadir=self._datadir,
        )
        self._reactor.addSystemEventTrigger("before", "shutdown", rpc.stop)

        deferred = rpc.start(self._reactor)
        return chain_function(deferred, self._start_session)

    def _start_session(self) -> Optional[Deferred]:
        if not self.rpc_router:
            self._stop_on_error("rpc", "RPC router is not available")
            return None

        crsb_user = self.rpc_router.cert_manager.CrossbarUsers.golemapp
        self.rpc_session = Session(
            self.rpc_router.address,
            cert_manager=self.rpc_router.cert_manager,
            use_ipv6=self._config_desc.use_ipv6,
            crsb_user=crsb_user,
            crsb_user_secret=self.rpc_router.cert_manager.get_secret(crsb_user)
        )
        deferred = self.rpc_session.connect()

        def on_connect(*_):
            methods = rpc_utils.object_method_map(self)
            methods['sys.exposed_procedures'] = \
                self.rpc_session.exposed_procedures
            self.rpc_session.add_procedures(methods)
            self._rpc_publisher = Publisher(self.rpc_session)
            StatusPublisher.set_publisher(self._rpc_publisher)

        return deferred.addCallbacks(on_connect, self._error('rpc session'))

    @rpc_utils.expose('golem.terms')
    @staticmethod
    def are_terms_accepted():
        return TermsOfUse.are_terms_accepted()

    @rpc_utils.expose('golem.terms.accept')
    def accept_terms(self,
                     enable_monitor: Optional[bool] = None,
                     enable_talkback: Optional[bool] = None) -> None:

        if enable_talkback is not None:
            self._config_desc.enable_talkback = enable_talkback
            self._use_talkback = enable_talkback

        if enable_monitor is not None:
            self._config_desc.enable_monitor = enable_monitor
            self._use_monitor = enable_monitor

        self._app_config.change_config(self._config_desc)
        return TermsOfUse.accept_terms()

    @rpc_utils.expose('golem.terms.show')
    @staticmethod
    def show_terms():
        return TermsOfUse.show_terms()

    @rpc_utils.expose('golem.version')
    @staticmethod
    def get_golem_version():
        return golem.__version__

    @rpc_utils.expose('golem.graceful_shutdown')
    def graceful_shutdown(self) -> ShutdownResponse:
        if self.client is None:
            logger.warning('Shutdown called when client=None, try again later')
            return ShutdownResponse.off

        # is in shutdown? turn off as toggle
        if self._config_desc.in_shutdown:
            self.client.update_setting('in_shutdown', False)
            logger.info('Turning off shutdown mode')
            return ShutdownResponse.off

        # is not providing nor requesting, normal shutdown
        if not self._is_task_in_progress():
            logger.info('Node not working, executing normal shutdown')
            self.quit()
            return ShutdownResponse.quit

        # configure in_shutdown
        logger.info('Enabling shutdown mode, no more tasks can be started')
        self.client.update_setting('in_shutdown', True)

        # subscribe to events

        return ShutdownResponse.on

    def _try_shutdown(self) -> None:
        # is not in shutdown?
        if not self._config_desc.in_shutdown:
            logger.debug('Checking shutdown, no shutdown configure')
            return

        if self._is_task_in_progress():
            logger.info('Shutdown checked, a task is still in progress')
            return

        logger.info('Node done with all tasks, shutting down')
        self.quit()

    def _is_task_in_progress(self) -> bool:
        if self.client is None:
            logger.debug('_is_task_in_progress? False: client=None')
            return False

        task_server = self.client.task_server
        if task_server is None or task_server.task_manager is None:
            logger.debug('_is_task_in_progress? False: task_manager=None')
            return False

        task_requestor_progress = task_server.task_manager.get_progresses()
        if task_requestor_progress:
            logger.debug('_is_task_in_progress? requestor=%r', True)
            return True

        if task_server.task_computer is None:
            logger.debug('_is_task_in_progress? False: task_computer=None')
            return False

        task_provider_progress = task_server.task_computer.assigned_subtask
        logger.debug('_is_task_in_progress? provider=%r, requestor=False',
                     task_provider_progress)
        return bool(task_provider_progress)

    @require_rpc_session()
    def _check_terms(self) -> Optional[Deferred]:

        def wait_for_terms():
            while not self.are_terms_accepted() and self._reactor.running:
                logger.info(
                    'Terms of use must be accepted before using Golem. '
                    'Run `golemcli terms show` to display the terms '
                    'and `golemcli terms accept` to accept them.')
                time.sleep(5)

        return threads.deferToThread(wait_for_terms)

    @require_rpc_session()
    def _start_keys_auth(self) -> Optional[Deferred]:

        def create_keysauth():
            # If keys_auth already exists it means we used command line flag
            # and don't need to inform client about required password
            if self.is_account_unlocked():
                return

            tip_msg = 'Run `golemcli account unlock` and enter your password.'

            if self.key_exists():
                event = 'get_password'
                tip_msg = 'Waiting for password to unlock the account. ' \
                          f'{tip_msg}'
            else:
                event = 'new_password'
                tip_msg = 'New account, waiting for password to be set. ' \
                          f'{tip_msg}'

            while not self.is_account_unlocked() and self._reactor.running:
                logger.info(tip_msg)
                StatusPublisher.publish(Component.client, event, Stage.pre)
                time.sleep(5)

            StatusPublisher.publish(Component.client, event, Stage.post)

        return threads.deferToThread(create_keysauth)

    def _start_docker(self) -> Optional[Deferred]:
        if not self._use_docker_manager:
            return None

        def start_docker():
            self._docker_manager = DockerManager.install(self._config_desc)
            self._docker_manager.check_environment()  # noqa pylint: disable=no-member

        return threads.deferToThread(start_docker)

    @require_rpc_session()
    def _setup_client(self, *_) -> None:

        if not self._keys_auth:
            self._error("KeysAuth is not available")
            return

        from golem.tools.talkback import enable_sentry_logger
        enable_sentry_logger(self._use_talkback)

        self.client = self._client_factory(self._keys_auth)
        self._reactor.addSystemEventTrigger("before", "shutdown",
                                            self.client.quit)

        self.client.set_rpc_publisher(self._rpc_publisher)

        golem_async.async_run(
            golem_async.AsyncRequest(self._run),
            error=self._error('Cannot start the client'),
        )

    @require_rpc_session()
    def _run(self, *_) -> None:
        if not self.client:
            self._stop_on_error("client", "Client is not available")
            return

        self._setup_apps()
        self.client.sync()

        try:
            self.client.start()
            for peer in self._peers:
                self.client.connect(peer)
        except SystemExit:
            self._reactor.callFromThread(self._reactor.stop)
            return

        methods = self.client.get_wamp_rpc_mapping()

        def rpc_ready(_):
            logger.info('All procedures registered in WAMP router')
            self._rpc_publisher.publish(
                rpceventnames.Golem.procedures_registered,
            )
        # pylint: disable=no-member
        self.rpc_session.add_procedures(methods).addCallback(  # type: ignore
            rpc_ready,
        )
        # pylint: enable=no-member

    def _setup_apps(self) -> None:
        if not self.client:
            self._stop_on_error("client", "Client is not available")
            return

        self.apps_manager.load_all_apps()

        for env in self.apps_manager.get_env_list():
            env.accept_tasks = True
            self.client.environments_manager.add_environment(env)

    def _error(self, msg: str) -> Callable:
        return functools.partial(self._stop_on_error, msg)

    def _stop_on_error(self, msg: str, err: Any) -> None:
        if self._reactor.running:
            exc_info = (err.type, err.value, err.getTracebackObject()) \
                if isinstance(err, Failure) else None
            logger.error(
                "Stopping because of %r error: %r", msg, err, exc_info=exc_info)
            self._reactor.callFromThread(self._reactor.stop)
