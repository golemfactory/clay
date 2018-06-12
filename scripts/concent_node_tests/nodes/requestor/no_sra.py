#!/usr/bin/env python
"""

Requestor Node that doesn't send `SubtaskResultsAccepted`

"""
import mock
import sys

from golem_messages.message.tasks import SubtaskResultsAccepted
from golem.task.tasksession import TaskSession
from scripts.concent_node_tests import params

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402

sys.argv.extend(params.REQUESTOR_ARGS)

original_send = TaskSession.send


def send(self, msg, send_unverified=False):

    # fail to send `SubtaskResultsAccepted`
    if isinstance(msg, SubtaskResultsAccepted):
        return

    original_send(self, msg, send_unverified=send_unverified)


with mock.patch("golem.task.tasksession.TaskSession.send", send):
    start()
