#!/usr/bin/env python
"""

Requestor Node not sending the sending out the payments

"""
import mock
import sys

from scripts.concent_integration_tests import params, helpers

sys.path.insert(0, 'golem')

from golemapp import start  # noqa: E402 module level import not at top of file

sys.argv.extend(params.REQUESTOR_ARGS_DEBUG)


with mock.patch(
        'golem.ethereum.paymentprocessor.PaymentProcessor.sendout',
        mock.Mock(return_value=True),
):
    start()
