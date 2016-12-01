import logging
import os
from collections import namedtuple

from crossbar.common import checkconfig
from crossbar.controller.cli import run_command_stop
from crossbar.controller.node import Node

logger = logging.getLogger('golem.rpc.crossbar')

CrossbarRouterOptions = namedtuple('CrossbarRouterOptions', ['cbdir', 'logdir', 'loglevel',
                                                             'cdc', 'argv', 'config'])


class LoggerBridge(object):

    def __getattr__(self, item):
        def bridge(_msg, *_, **kwargs):
            return getattr(logger, item)(_msg.format(**kwargs))
        return bridge


class CrossbarRouter(object):

    def __init__(self, datadir=None, crossbar_dir='crossbar', crossbar_log_level='trace'):

        if datadir:
            self.working_dir = os.path.join(datadir, crossbar_dir)
        else:
            self.working_dir = crossbar_dir

        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)

        if not os.path.isdir(self.working_dir):
            raise Exception("'{}' is not a directory".format(self.working_dir))

        self.log_level = crossbar_log_level
        self.options = self._build_options()
        self.config = self._build_config()
        self.node = None
        self.pubkey = None

    def start(self, reactor, callback, errback):
        reactor.callWhenRunning(self._start, self.options,
                                reactor,
                                callback, errback)

    def stop(self, exit=True, **kwargs):
        run_command_stop(self.options, exit=exit, **kwargs)

    def _start(self, options, reactor, callback, errback):
        self._start_node(options, reactor).addCallbacks(callback, errback)

    def _start_node(self, options, reactor):

        self.node = Node(options.cbdir, reactor=reactor)
        self.node.log = LoggerBridge()
        self.pubkey = self.node.maybe_generate_key(options.cbdir)

        checkconfig.check_config(self.config)
        self.node._config = self.config

        return self.node.start(cdc_mode=options.cdc)

    def _build_options(self):
        return CrossbarRouterOptions(
            self.working_dir,
            None,
            self.log_level,
            cdc=False,
            argv=None,
            config=None
        )

    @staticmethod
    def _build_config(host='localhost', port=61000):
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
                        'serializers': [u'msgpack'],
                        'endpoint': {
                            'type': u'tcp',
                            'port': port
                        },
                        'url': u'ws://{}:{}'.format(host, port),
                        'options': {
                            # FIXME: contstrain origins
                            'allowed_origins': u'*',
                            'enable_webstatus': True,
                        }
                    }
                ],
                'components': []
            }]
        }
