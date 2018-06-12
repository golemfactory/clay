#!/usr/bin/env python
"""

Requestor Node that fails to download the results.

"""

import mock
import sys

sys.path.insert(0, 'golem')

from golemapp import start
from scripts.concent_node_tests import params

sys.argv.extend(params.REQUESTOR_ARGS_DEBUG)


def pull_package(
        self, content_hash, task_id, subtask_id, key_or_secret,
        success, error, async_=True, client_options=None, output_dir=None):
    error('wrench in the gears')


with mock.patch("golem.task.result.resultmanager."
                "EncryptedResultPackageManager.pull_package",
                pull_package):
    start()
