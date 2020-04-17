#!/usr/bin/env python
"""

Provider node that refuses to compute the task
and sends OfferCancelled after receiving the TaskToCompute

"""

import inspect
import mock

from golem.task.taskcomputer import TaskComputerAdapter

from golemapp import main


original_can_take_work = TaskComputerAdapter.can_take_work


def can_take_work(self):
    fn = inspect.stack()[1].function
    if fn == '_react_to_task_to_compute':
        return False

    return original_can_take_work(self)


with mock.patch("golem.task.taskcomputer.TaskComputerAdapter.can_take_work",
                can_take_work):
    main()
