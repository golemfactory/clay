#!/usr/bin/env python
"""

Provider Node running a day in the past

"""
import freezegun
import sys

from scripts.concent_integration_tests import params, helpers

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.PROVIDER_ARGS_DEBUG)


with freezegun.freeze_time(helpers.yesterday(), tick=True):
    start()
