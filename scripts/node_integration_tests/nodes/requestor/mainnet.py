#!/usr/bin/env python
"""

Regular, unmodified Requestor node

"""

import sys
from scripts.node_integration_tests import params

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.REQUESTOR_ARGS_MAINNET_DEBUG)

start()
