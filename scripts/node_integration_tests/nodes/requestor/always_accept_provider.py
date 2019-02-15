#!/usr/bin/env python
import mock
import sys

from scripts.node_integration_tests import params

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.REQUESTOR_ARGS_DEBUG)

with mock.patch("golem.task.taskserver.TaskServer.should_accept_provider",
                mock.Mock(return_value=True)):
    start()
