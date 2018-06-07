#!/usr/bin/env python
"""

Regular, unmodified Requestor node

"""

import sys

sys.path.insert(0, 'golem')

from golemapp import start
from scripts.concent_node_tests import params

sys.argv.extend(params.REQUESTOR_ARGS)

start()
