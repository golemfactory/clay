#!/usr/bin/env python
"""

Requestor Node that doesn't send `AckReportComputedTask` in response to
Provider's `ReportComputedTask` message, thus triggering the Provider to
reach out to the Concent.

"""

import mock
import sys

from golem_messages.message import RandVal
from scripts.node_integration_tests import params

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.REQUESTOR_ARGS_DEBUG)

with mock.patch(
        "golem.task.tasksession.concent_helpers.process_report_computed_task",
        mock.Mock(return_value=RandVal())):
    start()
