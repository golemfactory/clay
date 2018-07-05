#!/usr/bin/env python
"""

Regular, unmodified Requestor node

"""

import sys
from scripts.concent_integration_tests import params

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.REQUESTOR_ARGS)

start()
