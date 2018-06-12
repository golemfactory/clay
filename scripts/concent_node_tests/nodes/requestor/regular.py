#!/usr/bin/env python
"""

Regular, unmodified Requestor node

"""

import sys
from scripts.concent_node_tests import params

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402

sys.argv.extend(params.REQUESTOR_ARGS)

start()
