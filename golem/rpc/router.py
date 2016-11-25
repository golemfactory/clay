import logging
import os
from collections import namedtuple

from crossbar.controller.cli import run_command_stop
from crossbar.controller.node import Node

logger = logging.getLogger('golem.rpc')

CrossbarRouterOptions = namedtuple('CrossbarRouterOptions', ['cbdir', 'logdir', 'loglevel',
                                                             'cdc', 'argv', 'config'])


class CrossbarRouter(object):

    def __init__(self, datadir=None, crossbar_dir='crossbar',
                 crossbar_log_dir='crossbar.logs', crossbar_log_level='trace'):

        if datadir:
            self.working_dir = os.path.join(datadir, crossbar_dir)
            self.log_dir = os.path.join(datadir, crossbar_log_dir)
        else:
            self.working_dir = crossbar_dir
            self.log_dir = crossbar_log_dir

        self.crossbar_log_level = crossbar_log_level

        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        if not os.path.isdir(self.working_dir):
            raise "Provided Crossbar dir '{}' is not a directory".format(self.working_dir)
        if not os.path.isdir(self.log_dir):
            raise "Provided Crossbar log dir '{}' is not a directory".format(self.log_dir)

        self.options = self._build_options()
        self.node = None
        self.pubkey = None

    def start(self, reactor, callback, errback):
        reactor.callWhenRunning(self._start_router, self.options,
                                reactor,
                                callback, errback)

    def stop(self, exit=True, **kwargs):
        run_command_stop(self.options, exit=exit, **kwargs)

    def _build_options(self):
        return CrossbarRouterOptions(
            self.working_dir,
            self.log_dir,
            self.crossbar_log_level,
            cdc=False,
            argv=None,
            config=None
        )

    def _start_router(self, options, reactor, callback, errback):
        self._start_node(options, reactor).addCallbacks(callback, errback)

    def _start_node(self, options, reactor):
        self.node = Node(options.cbdir, reactor=reactor)
        self.pubkey = self.node.maybe_generate_key(options.cbdir)

        try:
            self.node.load(options.config)
        except Exception as e:
            logger.error("Error loading Crossbar node: {}".format(e))
            raise

        return self.node.start(cdc_mode=options.cdc)
