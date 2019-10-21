#!/usr/bin/env python
"""

Requestor Node that doesn't send `AckReportComputedTask` in response to
Provider's `ReportComputedTask` message, thus triggering the Provider to
reach out to the Concent.

"""

import mock

from golem_messages.message import RandVal

from golemapp import main  # noqa: E402 module level import not at top of file

with mock.patch(
        "golem.task.tasksession.concent_helpers.process_report_computed_task",
        mock.Mock(return_value=RandVal())):
    main()
