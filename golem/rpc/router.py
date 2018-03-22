import logging
import os
from collections import namedtuple
from typing import Iterable, Optional

from crossbar.common import checkconfig
from twisted.internet.defer import inlineCallbacks

from golem.rpc.cert import CertificateManager
from golem.rpc.common import CROSSBAR_DIR, CROSSBAR_REALM, CROSSBAR_HOST, \
    CROSSBAR_PORT
from golem.rpc.session import WebSocketAddress

logger = logging.getLogger('golem.rpc.crossbar')

CrossbarRouterOptions = namedtuple(
    'CrossbarRouterOptions',
    ['cbdir', 'logdir', 'loglevel', 'argv', 'config']
)


class CrossbarRouter(object):

    serializers = ['msgpack']

    def __init__(self,  # pylint: disable=too-many-arguments
                 host: str = CROSSBAR_HOST,
                 port: int = CROSSBAR_PORT,
                 realm: str = CROSSBAR_REALM,
                 datadir: Optional[str] = None,
                 crossbar_dir: str = CROSSBAR_DIR,
                 crossbar_log_level: str = 'info',
                 ssl: bool = True) -> None:

        if datadir:
            self.working_dir = os.path.join(datadir, crossbar_dir)
        else:
            self.working_dir = crossbar_dir

        os.makedirs(self.working_dir, exist_ok=True)
        if not os.path.isdir(self.working_dir):
            raise IOError("'{}' is not a directory".format(self.working_dir))

        self.cert_manager = CertificateManager(self.working_dir)
        self.address = WebSocketAddress(host, port, realm, ssl)

        self.log_level = crossbar_log_level
        self.node = None
        self.pubkey = None

        self.options = self._build_options()
        self.config = self._build_config(self.address,
                                         self.serializers,
                                         self.cert_manager)

        logger.debug('xbar init with cfg: %s', self.config)

    def start(self, reactor, options=None):
        # imports reactor
        from crossbar.controller.node import Node, default_native_workers

        options = options or self.options
        if self.address.ssl:
            self.cert_manager.generate_if_needed()

        self.node = Node(options.cbdir, reactor=reactor)
        self.pubkey = self.node.maybe_generate_key(options.cbdir)

        workers = default_native_workers()

        checkconfig.check_config(self.config, workers)
        self.node._config = self.config
        return self.node.start()

    @inlineCallbacks
    def stop(self):
        yield self.node._controller.shutdown()  # noqa # pylint: disable=protected-access

    def _build_options(self, argv=None, config=None):
        return CrossbarRouterOptions(
            cbdir=self.working_dir,
            logdir=None,
            loglevel=self.log_level,
            argv=argv,
            config=config
        )

    @staticmethod
    def _build_config(address: WebSocketAddress,
                      serializers: Iterable[str],
                      cert_manager: CertificateManager,
                      realm: str = CROSSBAR_REALM,
                      enable_webstatus: bool = False):

        allowed_origins = [
            address.host,
            address.host + ':*',
            'http://' + address.host,
            'http://' + address.host + ':*',
            'https://' + address.host,
            'https://' + address.host + ':*',
        ]

        ws_endpoint = {
            'type': 'tcp',
            'interface': address.host,
            'port': address.port,
        }

        if address.ssl:
            ws_endpoint["tls"] = {
                "key": cert_manager.key_path,
                "certificate": cert_manager.cert_path,
                "dhparam": cert_manager.dh_path,
            }

        return {
            'version': 2,
            'controller': {
                'options': {
                    'shutdown': ['shutdown_on_shutdown_requested']
                }
            },
            'workers': [{
                'type': 'router',
                'options': {
                    'title': 'Golem'
                },
                'transports': [{
                    'type': 'websocket',
                    'serializers': serializers,
                    'endpoint': ws_endpoint,
                    'url': str(address),
                    'options': {
                        'allowed_origins': allowed_origins,
                        'enable_webstatus': enable_webstatus,
                    }
                }],
                'components': [],
                "realms": [{
                    "name": realm,
                    "roles": [{
                        "name": 'anonymous',
                        "permissions": [{
                            "uri": '*',
                            "allow": {
                                "call": True,
                                "register": True,
                                "publish": True,
                                "subscribe": True
                            }
                        }]
                    }]
                }],
            }]
        }
