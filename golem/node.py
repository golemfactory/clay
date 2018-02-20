import logging

from apps.appsmanager import AppsManager
from golem.client import Client
from golem.core.async import async_callback
from golem.docker.manager import DockerManager
from golem.rpc.mapping.rpcmethodnames import CORE_METHOD_MAP
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import object_method_map, Session

logger = logging.getLogger("app")


class Node(object):
    """ Simple Golem Node connecting console user interface with Client
    :type client golem.client.Client:
    """

    def __init__(  # pylint: disable=too-many-arguments
            self,
            datadir,
            config_desc,
            peers=None,
            transaction_system=False,
            use_monitor=False,
            use_docker_machine_manager=True,
            start_geth=False,
            start_geth_port=None,
            geth_address=None):

        # DO NOT MAKE THIS IMPORT GLOBAL
        # otherwise, reactor will install global signal handlers on import
        # and will install the default version of the reactor
        # instead of the desired one
        from twisted.internet import reactor

        self._reactor = reactor
        self._config_desc = config_desc
        self._datadir = datadir

        self.client = None
        self._client_factory = lambda: Client(
            datadir=datadir,
            config_desc=config_desc,
            transaction_system=transaction_system,
            use_docker_machine_manager=use_docker_machine_manager,
            use_monitor=use_monitor,
            start_geth=start_geth,
            start_geth_port=start_geth_port,
            geth_address=geth_address,
        )

        self.rpc_router = None
        self.rpc_session = None

        self._peers = peers or []
        self._apps_manager = None

    def run(self):
        try:
            self._setup_rpc()
            self._reactor.run()
        except Exception as exc:
            logger.exception("Application error: %r", exc)

    def _run(self, *_):
        if self.client.use_docker_machine_manager:
            self._setup_docker()
        self._setup_apps()

        self.client.sync()

        try:
            self.client.start()
            for peer in self._peers:
                self.client.connect(peer)
        except SystemExit:
            self._reactor.callFromThread(self._reactor.stop)

    def _setup_rpc(self):
        self.rpc_router = CrossbarRouter(
            host=self._config_desc.rpc_address,
            port=self._config_desc.rpc_port,
            datadir=self._datadir,
        )
        self.rpc_router.start(self._reactor, self._rpc_router_ready,
                              self._rpc_error)
        self._reactor.addSystemEventTrigger(
            "before",
            "shutdown",
            self.rpc_router.stop,
        )

    def _setup_docker(self):
        docker_manager = DockerManager.install(self.client.config_desc)
        docker_manager.check_environment()

    def _setup_apps(self):
        self._apps_manager = AppsManager()
        self._apps_manager.load_apps()

        for env in self._apps_manager.get_env_list():
            env.accept_tasks = True
            self.client.environments_manager.add_environment(env)

    def _rpc_router_ready(self, *_):
        self.client = self._client_factory()
        self._reactor.addSystemEventTrigger("before", "shutdown",
                                            self.client.quit)

        methods = object_method_map(self.client, CORE_METHOD_MAP)
        self.rpc_session = Session(self.rpc_router.address, methods=methods)
        self.client.configure_rpc(self.rpc_session)
        self.rpc_session.connect().addCallbacks(async_callback(self._run),
                                                self._rpc_error)

    def _rpc_error(self, err):
        logger.error("RPC error: %r", err)
