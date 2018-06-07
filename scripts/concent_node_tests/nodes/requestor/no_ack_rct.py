#!/usr/bin/env python
"""

Requestor Node that doesn't send `AckReportComputedTask` in response to
Provider's `ReportComputedTask` message, thus triggering the Provider to
reach out to the Concent.

"""

import mock
import sys

sys.path.insert(0, 'golem')

from golem_messages.message import RandVal

from golemapp import start
from scripts.concent_node_tests import params

sys.argv.extend(params.REQUESTOR_ARGS)

with mock.patch(
        "golem.task.tasksession.concent_helpers.process_report_computed_task",
        mock.Mock(return_value=RandVal())):
    start()
