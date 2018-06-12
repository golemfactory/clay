#!/usr/bin/env python
"""

Provider node that sends `ForceReportComputedTask` almost immediately after
it doesn't receive the `AckReportComputedTask` - the message delay is reduced
to 10 seconds.

"""

import collections
import datetime
import mock
import sys

from golem_messages.message.concents import ForceReportComputedTask
from scripts.concent_node_tests import params

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402

sys.argv.extend(params.PROVIDER_ARGS_DEBUG)

with mock.patch(
        "golem.network.concent.client.MSG_DELAYS",
        collections.defaultdict(
            lambda: datetime.timedelta(0),
            {
                ForceReportComputedTask: datetime.timedelta(seconds=10),
            },
        )):
    start()
