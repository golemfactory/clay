#!/usr/bin/env python
"""

Requestor Node not sending out the payments

"""
import mock

from golemapp import main  # noqa: E402 module level import not at top of file


with mock.patch(
        'golem.ethereum.paymentprocessor.PaymentProcessor.sendout',
        mock.Mock(return_value=True),
):
    main()
