#!/usr/bin/env python
"""

Requestor Node running a day in the past
and not sending out the payments

"""
import freezegun
import mock

from scripts.node_integration_tests import helpers

from golemapp import main  # noqa: E402 module level import not at top of file


with freezegun.freeze_time(helpers.yesterday(), tick=True, ignore=['raven']):
    with mock.patch(
            'golem.ethereum.paymentprocessor.PaymentProcessor.sendout',
            mock.Mock(return_value=True),
    ):
        main()
