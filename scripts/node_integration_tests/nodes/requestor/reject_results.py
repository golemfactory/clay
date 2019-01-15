#!/usr/bin/env python
"""

Requestor Node that fails the verification of the results,
iow, always sends `SubtaskResultsRejected`.

"""

import mock
import sys

from golem.task.tasksession import TaskSession

from scripts.node_integration_tests import params

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.REQUESTOR_ARGS_DEBUG)

original_init = TaskSession.__init__


def ts_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)

    def _verify_subtask(*_, **__):
        return False

    self.task_manager.verify_subtask = _verify_subtask


with mock.patch("golem.task.tasksession.TaskSession.__init__", ts_init):
    start()
