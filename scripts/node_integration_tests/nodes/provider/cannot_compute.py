#!/usr/bin/env python
"""

Provider node that refuses to compute the task
because of a docker image problem

"""

import mock

from golem_messages import message

from golemapp import main


def wrong_docker_images(self, ctd):
    self.err_msg = message.CannotComputeTask.REASON.WrongDockerImages
    return False


with mock.patch("golem.task.tasksession.TaskSession._set_env_params",
                wrong_docker_images):
    main()
