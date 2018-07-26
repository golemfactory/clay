#!/usr/bin/env python
"""

Requestor Node running a day in the past
and not sending the sending out the payments

"""
import freezegun
import mock
import sys

from scripts.concent_integration_tests import params, helpers

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.REQUESTOR_ARGS_DEBUG)


with freezegun.freeze_time(helpers.yesterday(), tick=True):
    with mock.patch(
            'golem.ethereum.paymentprocessor.PaymentProcessor.sendout',
            mock.Mock(return_value=True),
    ):
        start()
