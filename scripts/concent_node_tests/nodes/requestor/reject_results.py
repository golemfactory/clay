#!/usr/bin/env python
"""

Requestor Node that sends fails the verification

"""

import mock
import sys

sys.path.insert(0, 'golem')

from golemapp import start
from scripts.concent_node_tests import params

sys.argv.extend(params.REQUESTOR_ARGS_DEBUG)


with mock.patch("golem.task.taskmanager.TaskManager.verify_subtask",
                mock.Mock(return_value=False)):
    start()
