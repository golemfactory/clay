import pickle
import unittest

from golem_messages import message
from golem_messages import factories as msg_factories
from golem_messages.shortcuts import dump, load

from .base import ConcentBaseTest


class ConcentBaseTestTest(ConcentBaseTest, unittest.TestCase):
    def test_assert_methods(self):
        requestor_keys = self._fake_keys()
        provider_keys = self._fake_keys()
        concent_keys = self._fake_keys()

        rct = msg_factories.tasks.ReportComputedTaskFactory()

        dump(rct, provider_keys.raw_privkey, requestor_keys.raw_pubkey)

        stored_rct = pickle.loads(pickle.dumps(rct))

        frct_concent = message.concents.ForceReportComputedTask(
            report_computed_task=rct
        )

        frct_concent_data = dump(
            frct_concent, provider_keys.raw_privkey, concent_keys.raw_pubkey)

        stored_frct = pickle.loads(pickle.dumps(frct_concent))

        frct_concent_rcv = load(
            frct_concent_data,
            concent_keys.raw_privkey,
            provider_keys.raw_pubkey
        )

        concent_rct = frct_concent_rcv.report_computed_task

        frct_requestor = message.concents.ForceReportComputedTask(
            report_computed_task=concent_rct)
        frct_requestor_data = dump(
            frct_requestor, concent_keys.raw_privkey, requestor_keys.raw_pubkey
        )
        frct_requestor_rcv = load(
            frct_requestor_data,
            requestor_keys.raw_privkey,
            concent_keys.raw_pubkey
        )

        self.assertEqual(frct_requestor_rcv.report_computed_task, stored_rct)
        self.assertNotEqual(frct_requestor_rcv, stored_frct)
        self.assertSamePayload(frct_requestor_rcv, stored_frct)
