#!/usr/bin/env python
"""

Requestor Node that fails the verification of the results,
iow, always sends `SubtaskResultsRejected`.

"""

import mock

from golem.task.tasksession import TaskSession

from golemapp import main  # noqa: E402 module level import not at top of file

original_init = TaskSession.__init__


def ts_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)

    def _verify_subtask(*_, **__):
        return False

    self.task_manager.verify_subtask = _verify_subtask


with mock.patch("golem.task.tasksession.TaskSession.__init__", ts_init):
    main()
