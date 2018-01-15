import logging
import os
from collections import namedtuple

from crossbar.common import checkconfig
from crossbar.controller.node import Node, default_native_workers
from twisted.internet.defer import inlineCallbacks

from golem.rpc.session import WebSocketAddress

logger = logging.getLogger('golem.rpc.crossbar')

CrossbarRouterOptions = namedtuple('CrossbarRouterOptions', ['cbdir', 'logdir', 'loglevel',
                                                             'argv', 'config'])


class CrossbarRouter(object):

    serializers = ['msgpack']

    def __init__(self, host='localhost', port=61000, realm='golem',
                 datadir=None, crossbar_dir='crossbar', crossbar_log_level='trace'):
        if datadir:
            self.working_dir = os.path.join(datadir, crossbar_dir)
        else:
            self.working_dir = crossbar_dir

        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)

        if not os.path.isdir(self.working_dir):
            raise IOError("'{}' is not a directory".format(self.working_dir))

        self.address = WebSocketAddress(host, port, realm)
        self.log_level = crossbar_log_level
        self.node = None
        self.pubkey = None

        self.options = self._build_options()
        self.config = self._build_config(self.address, self.serializers)
        logger.debug('xbar init with cfg: %s', self.config)

    def start(self, reactor, callback, errback):
        reactor.callWhenRunning(self._start,
                                self.options,
                                reactor,
                                callback, errback)

    @inlineCallbacks
    def stop(self):
        yield self.node._controller.shutdown()

    def _start(self, options, reactor, callback, errback):
        self._start_node(options, reactor).addCallbacks(callback, errback)

    def _start_node(self, options, reactor):
        self.node = Node(options.cbdir, reactor=reactor)
        self.pubkey = self.node.maybe_generate_key(options.cbdir)

        workers = default_native_workers()

        checkconfig.check_config(self.config, workers)
        self.node._config = self.config
        return self.node.start()

    def _build_options(self, argv=None, config=None):
        return CrossbarRouterOptions(
            cbdir=self.working_dir,
            logdir=None,
            loglevel=self.log_level,
            argv=argv,
            config=config
        )

    @staticmethod
    def _build_config(address, serializers, allowed_origins='*', realm='golem', enable_webstatus=False):
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
                'transports': [
                    {
                        'type': 'websocket',
                        'serializers': serializers,
                        'endpoint': {
                            'type': 'tcp',
                            'interface': str(address.host),
                            'port': address.port
                        },
                        'url': str(address),
                        'options': {
                            'allowed_origins': allowed_origins,
                            'enable_webstatus': enable_webstatus,
                        }
                    }
                ],
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
