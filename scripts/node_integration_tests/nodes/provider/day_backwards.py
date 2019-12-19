#!/usr/bin/env python
"""

Provider Node running a day in the past

"""
import freezegun

from scripts.node_integration_tests import helpers

from golemapp import main  # noqa: E402 module level import not at top of file

with freezegun.freeze_time(helpers.yesterday(), tick=True, ignore=['raven']):
    main()
