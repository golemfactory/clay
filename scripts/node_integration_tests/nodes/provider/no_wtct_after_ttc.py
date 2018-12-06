#!/usr/bin/env python
"""

Provider node failing the subtask

"""
import mock
import sys

from golem_messages.message.tasks import WantToComputeTask, TaskToCompute
from golem.task.tasksession import TaskSession
from scripts.node_integration_tests import params

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.PROVIDER_ARGS_DEBUG)

original_send = TaskSession.send
original_interpret = TaskSession.interpret
received_ttc = False


def send(self, msg, *args, **kwargs):
    # fail to send `WantToComputeTask` once `TaskToCompute` has been received
    if received_ttc and isinstance(msg, WantToComputeTask):
        return

    original_send(self, msg, *args, **kwargs)


def interpret(self, msg, *args, **kwargs):
    global received_ttc

    if isinstance(msg, TaskToCompute):
        received_ttc = True

    original_interpret(self, msg, *args, **kwargs)


@mock.patch("golem.task.tasksession.TaskSession.interpret", interpret)
@mock.patch("golem.task.tasksession.TaskSession.send", send)
def start_node(*_):
    start()


start_node()
