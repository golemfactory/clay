#!/usr/bin/env python
"""

Regular, unmodified Provider node, running with DEBUG loglevel

"""

import sys

sys.path.insert(0, 'golem')

from golemapp import start
from scripts.concent_node_tests import params

sys.argv.extend(params.PROVIDER_ARGS_DEBUG)

start()
