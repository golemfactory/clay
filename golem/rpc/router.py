import logging
import os
from collections import namedtuple

from crossbar.common import checkconfig
from crossbar.controller.node import Node
from twisted.internet.defer import inlineCallbacks

from golem.rpc.session import WebSocketAddress

logger = logging.getLogger('golem.rpc.crossbar')

CrossbarRouterOptions = namedtuple('CrossbarRouterOptions', ['cbdir', 'logdir', 'loglevel',
                                                             'argv', 'config'])


class LoggerBridge(object):

    def __getattr__(self, item):
        def bridge(_msg, *_, **kwargs):
            attr = 'error' if not hasattr(logger, item) else item
            kwargs = {k: v for k, v in kwargs.iteritems()
                      if '{{{k}}}'.format(k=k) in _msg}
            return getattr(logger, attr)(_msg.format(**kwargs))
        return bridge


class CrossbarRouter(object):

    serializers = [u'msgpack']

    def __init__(self, host='localhost', port=61000, realm=u'golem',
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
        self.node.log = LoggerBridge()
        self.pubkey = self.node.maybe_generate_key(options.cbdir)

        checkconfig.check_config(self.config)
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
    def _build_config(address, serializers, allowed_origins=u'*', realm=u'golem', enable_webstatus=False):
        return {
            'version': 2,
            'workers': [{
                'type': u'router',
                'options': {
                    'title': u'Golem'
                },
                'transports': [
                    {
                        'type': u'websocket',
                        'serializers': serializers,
                        'endpoint': {
                            'type': u'tcp',
                            'interface': unicode(address.host),
                            'port': address.port
                        },
                        'url': unicode(address),
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
                        "name": u'anonymous',
                        "permissions": [{
                            "uri": u'*',
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
