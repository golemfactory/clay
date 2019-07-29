#!/usr/bin/env python
"""

Requestor Node that fails to download the results.

"""

import mock
import time

from golemapp import main  # noqa: E402 module level import not at top of file


def pull_package(
        self, content_hash, task_id, subtask_id, key_or_secret,
        success, error, async_=True, client_options=None, output_dir=None):
    time.sleep(3)
    error('wrench in the gears')


with mock.patch("golem.task.result.resultmanager."
                "EncryptedResultPackageManager.pull_package",
                pull_package):
    main()
