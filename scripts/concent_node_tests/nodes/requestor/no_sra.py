#!/usr/bin/env python
"""

Requestor Node that doesn't send `SubtaskResultsAccepted`

"""
import mock
import sys


sys.path.insert(0, 'golem')

from golem_messages.message.tasks import SubtaskResultsAccepted
from golem.task.tasksession import TaskSession

from golemapp import start
from scripts.concent_node_tests import params

sys.argv.extend(params.REQUESTOR_ARGS)


def send(self, msg, send_unverified=False):

    # fail to send `SubtaskResultsAccepted`
    if isinstance(msg, SubtaskResultsAccepted):
        return

    TaskSession.send(self, msg, send_unverified=send_unverified)


with mock.patch("golem.task.tasksession.TaskSession.send", send):
    start()
