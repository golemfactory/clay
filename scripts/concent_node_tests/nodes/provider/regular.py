#!/usr/bin/env python
"""

Regular, unmodified Provider node

"""

import sys
from scripts.concent_node_tests import params

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.PROVIDER_ARGS)

start()
