#!/usr/bin/env python
"""

Provider node failing the subtask

"""
import mock
import sys

from golem_messages.message.tasks import WantToComputeTask, ReportComputedTask
from golem.task.tasksession import TaskSession
from scripts.node_integration_tests import params

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.PROVIDER_ARGS_DEBUG)

original_send = TaskSession.send
counter = 0


def send(self, msg, *args, **kwargs):
    global counter

    # fail to send `WantToComputeTask` the _second_ time
    if isinstance(msg, WantToComputeTask):
        counter += 1
        print(counter)
        if 7 > counter > 1:
            return

    original_send(self, msg, *args, **kwargs)


with mock.patch("golem.task.tasksession.TaskSession.send", send):
    start()
