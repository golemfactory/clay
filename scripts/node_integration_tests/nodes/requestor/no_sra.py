#!/usr/bin/env python
"""

Requestor Node that doesn't send `SubtaskResultsAccepted`

"""
import mock

from golem_messages.message.tasks import SubtaskResultsAccepted
from golem.task.tasksession import TaskSession

from golemapp import main  # noqa: E402 module level import not at top of file

original_send = TaskSession.send


def send(self, msg, *args, **kwargs):

    # fail to send `SubtaskResultsAccepted`
    if isinstance(msg, SubtaskResultsAccepted):
        return

    original_send(self, msg, *args, **kwargs)


with mock.patch("golem.task.tasksession.TaskSession.send", send):
    main()
