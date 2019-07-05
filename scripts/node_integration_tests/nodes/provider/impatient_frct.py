#!/usr/bin/env python
"""

Provider node that sends `ForceReportComputedTask` almost immediately after
it doesn't receive the `AckReportComputedTask` - the message delay is reduced
to 10 seconds.

"""

import collections
import datetime
import mock

from golem_messages.message.concents import ForceReportComputedTask

from golemapp import main

with mock.patch(
        "golem.network.concent.client.MSG_DELAYS",
        collections.defaultdict(
            lambda: datetime.timedelta(0),
            {
                ForceReportComputedTask: datetime.timedelta(seconds=10),
            },
        )):
    main()
