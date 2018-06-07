#!/usr/bin/env python
import collections
import datetime
import mock
import sys

sys.path.insert(0, 'golem')

from golemapp import start
from golem_messages.message import RandVal
from golem_messages.message.concents import ForceReportComputedTask
from scripts.concent_node_tests import params

sys.argv.extend(params.REQUESTOR_ARGS)

with mock.patch(
        "golem.task.tasksession.concent_helpers.process_report_computed_task",
        mock.Mock(return_value=RandVal())):
    with mock.patch(
            "golem.network.concent.client.MSG_DELAYS",
            collections.defaultdict(
                lambda: datetime.timedelta(0),
                {
                    ForceReportComputedTask: datetime.timedelta(seconds=10),
                },
            )):
        start()
