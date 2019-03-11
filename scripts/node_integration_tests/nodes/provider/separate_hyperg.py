#!/usr/bin/env python
"""

Regular, unmodified Provider node, running with DEBUG loglevel

"""

import sys

from scripts.node_integration_tests import params

from golemapp import start

args = list(params.PROVIDER_ARGS_DEBUG)
args.extend([
    '--hyperdrive-port', '3283',
    '--hyperdrive-rpc-port', '3293'
])

sys.argv.extend(args)

start()
