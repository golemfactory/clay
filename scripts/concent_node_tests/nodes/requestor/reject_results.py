#!/usr/bin/env python
"""

Requestor Node that fails the verification of the results,
iow, always sends `SubtaskResultsRejected`.

"""

import mock
import sys

from scripts.concent_node_tests import params

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.REQUESTOR_ARGS_DEBUG)


with mock.patch("golem.task.taskmanager.TaskManager.verify_subtask",
                mock.Mock(return_value=False)):
    start()
