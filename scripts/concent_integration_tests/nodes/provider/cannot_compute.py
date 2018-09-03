#!/usr/bin/env python
"""

Provider node that refuses to compute the task
because of a docker image problem

"""

import mock
import sys

from golem_messages import message
from scripts.concent_integration_tests import params

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.PROVIDER_ARGS_DEBUG)


def wrong_docker_images(self, ctd):
    self.err_msg = message.CannotComputeTask.REASON.WrongDockerImages
    return False


with mock.patch("golem.task.tasksession.TaskSession._set_env_params",
                wrong_docker_images):
    start()
