# pylint: disable=no-value-for-parameter
import logging
import sys
import time
import unittest

from golem_messages import cryptography
from golem_messages import factories as msg_factories
from golem_messages import message
from golem_messages.utils import encode_hex as encode_key_id
import golem_sci.structs

from golem.network.concent import exceptions as concent_exceptions

from ..base import SCIBaseTest


fpr_reasons = message.concents.ForcePaymentRejected.REASON
logger = logging.getLogger(__name__)
sr_reasons = message.concents.ServiceRefused.REASON


class ForcePaymentBase(SCIBaseTest):
    def assertPaymentRejected(
            self,
            msg: message.concents.ForcePayment,
            reason=None,
        ):
        response = self.provider_load_response(self.provider_send(msg))
        self.assertIsInstance(response, message.concents.ForcePaymentRejected)
        if reason:
            self.assertEqual(response.reason, reason)
        return response

    def assertServiceRefused(
            self,
            msg: message.concents.ServiceRefused,
            reason=None,
        ):
        self.assertIsInstance(msg, message.concents.ServiceRefused)
        if reason:
            self.assertEqual(msg.reason, reason)

    def _prepare_list_of_acceptances(self):
        LOA = []
        for _ in range(3):
            rct = msg_factories.tasks.ReportComputedTaskFactory(
                **self.gen_rtc_kwargs(),
                **self.gen_ttc_kwargs('task_to_compute__'),
                task_to_compute__ethsig__privkey=self.requestor_priv_key,
            )
            sra = msg_factories.tasks.SubtaskResultsAcceptedFactory(
                report_computed_task=rct,
                payment_ts=int(time.time()) - 3600 * 24,
            )
            sra.sign_message(self.requestor_priv_key)
            LOA.append(sra)
        return LOA

    def _perform_payments_scenario(self, acceptances, expected_amount_paid,
                                   expected_amount_pending):
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=acceptances,
        )
        response_provider = self.provider_load_response(self.provider_send(fp))
        response_requestor = self.requestor_receive()
        roles = message.concents.ForcePaymentCommitted.Actor
        for response in (response_provider, response_requestor):
            self.assertIsInstance(
                response,
                message.concents.ForcePaymentCommitted,
            )
            self.assertEqual(
                response.payment_ts,
                max(sra.payment_ts for sra in acceptances),
            )
            self.assertEqual(
                response.task_owner_key,
                self.requestor_pub_key,
            )
            self.assertEqual(
                response.provider_eth_account,
                acceptances[0].task_to_compute.provider_ethereum_address,
            )
            self.assertEqual(
                response.amount_paid,
                expected_amount_paid,
            )
            self.assertEqual(
                response.amount_pending,
                expected_amount_pending,
            )
        self.assertEqual(response_provider.recipient_type, roles.Provider)
        self.assertEqual(response_requestor.recipient_type, roles.Requestor)


class RequestorDoesntPayTestCase(ForcePaymentBase):
    def test_empty_list(self):
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[],
        )
        with self.assertRaises(concent_exceptions.ConcentRequestError):
            self.provider_load_response(self.provider_send(fp))

    @unittest.skip('Not implemented')
    def test_provider_deposit(self):
        pass  # TODO

    def test_multiple_requestors(self):
        """Test requestor sameness

        Concent service verifies wether all messages from LAR are signed by
        the same Requestor and are have the same Ethereum address. Otherwise
        Concent responds with ServiceRefused "invalid message".

        LAR - list of acceptances in request
        """
        rct = msg_factories.tasks.ReportComputedTaskFactory(
            **self.gen_rtc_kwargs(),
            **self.gen_ttc_kwargs('task_to_compute__'),
            task_to_compute__ethsig__privkey=self.requestor_priv_key,
        )
        sra1 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            report_computed_task=rct,
            payment_ts=int(time.time()) - 3600*24,
        )
        sra1.sign_message(self.requestor_priv_key)

        requestor2_keys = cryptography.ECCx(None)
        ttc2_kwargs = self.gen_ttc_kwargs('task_to_compute__')
        ttc2_kwargs.update({
            'task_to_compute__sign__privkey': requestor2_keys.raw_privkey,
            'task_to_compute__requestor_public_key': encode_key_id(
                requestor2_keys.raw_pubkey,
            ),
            'task_to_compute__requestor_ethereum_public_key': encode_key_id(
                requestor2_keys.raw_pubkey,
            ),
            'task_to_compute__ethsig__privkey': requestor2_keys.raw_privkey,
        })
        rct2 = msg_factories.tasks.ReportComputedTaskFactory(
            **self.gen_rtc_kwargs(),
            **ttc2_kwargs,
        )
        sra2 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            report_computed_task=rct2,
            payment_ts=int(time.time()) - 3600*24,
        )
        sra2.sign_message(requestor2_keys.raw_privkey)
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[
                sra1, sra2,
            ],
        )
        self.assertTrue(
            fp.subtask_results_accepted_list[0].verify_signature(  # noqa pylint:disable=no-member
                self.requestor_pub_key
            )
        )
        self.assertTrue(
            fp.subtask_results_accepted_list[1].verify_signature(  # noqa pylint:disable=no-member
                requestor2_keys.raw_pubkey
            )
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertServiceRefused(response)

    def test_multiple_eth_accounts(self):
        ttc_kwargs = self.gen_ttc_kwargs('task_to_compute__')
        provider1_keys = cryptography.ECCx(None)
        ttc_kwargs.update({
            'task_to_compute__'
            'want_to_compute_task__'
            'provider_ethereum_public_key': encode_key_id(
                provider1_keys.raw_pubkey
            ),
        })
        rct = msg_factories.tasks.ReportComputedTaskFactory(
            sign__privkey=provider1_keys.privkey,
            **ttc_kwargs,
            task_to_compute__ethsig__privkey=self.requestor_priv_key,
        )
        sra1 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            report_computed_task=rct,
            payment_ts=int(time.time()) - 3600*24,
        )
        sra1.sign_message(self.requestor_priv_key)
        ttc2_kwargs = self.gen_ttc_kwargs('task_to_compute__')
        provider2_keys = cryptography.ECCx(None)
        ttc2_kwargs.update({
            'task_to_compute__'
            'want_to_compute_task__'
            'provider_ethereum_public_key': encode_key_id(
                provider2_keys.raw_pubkey
            ),
        })
        rct2 = msg_factories.tasks.ReportComputedTaskFactory(
            sign__privkey=provider2_keys.privkey,
            **ttc2_kwargs,
            task_to_compute__ethsig__privkey=self.requestor_priv_key,
        )
        sra2 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            report_computed_task=rct2,
            payment_ts=int(time.time()) - 3600*24,
        )
        sra2.sign_message(self.requestor_priv_key)
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[
                sra1, sra2,
            ],
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertServiceRefused(response)

    def test_provider_asks_too_early(self):
        """Test messages due date

        Concent service verifies wether all messages from LAO are due.
        It responds with ForcePaymentRejected TimestampError otherwise.
        """
        rct = msg_factories.tasks.ReportComputedTaskFactory(
            **self.gen_rtc_kwargs(),
            **self.gen_ttc_kwargs('task_to_compute__'),
            task_to_compute__ethsig__privkey=self.requestor_priv_key,
        )
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            report_computed_task=rct,
            payment_ts=int(time.time()) - 100,
        )
        sra.sign_message(self.requestor_priv_key)
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[
                sra,
            ],
        )
        response = self.assertPaymentRejected(fp, fpr_reasons.TimestampError)
        self.assertEqual(response.force_payment, fp)

    def test_force_payment_committed_requestor_has_more_funds(self):
        """Concent service commits forced payment

        If deposit is higher or equal to V then V is paid to provider.
        Otherwise maximum available amount is transferred to provider.
        Both Requestor and Provider should receive ForcePaymentCommitted.
        """

        LOA = self._prepare_list_of_acceptances()
        V = sum(sra.task_to_compute.price for sra in LOA)
        self.put_deposit(self.requestor_sci, V + 10)
        self._perform_payments_scenario(LOA, V, 0)

    def test_force_payment_committed_requestor_has_exact_funds(self):
        LOA = self._prepare_list_of_acceptances()
        V = sum(sra.task_to_compute.price for sra in LOA)
        self.put_deposit(self.requestor_sci, V)
        self._perform_payments_scenario(LOA, V, 0)

    def test_force_payment_committed_requestor_has_insufficient_funds(self):
        LOA = self._prepare_list_of_acceptances()
        V = sum(sra.task_to_compute.price for sra in LOA)
        requestors_funds = V - 10
        self.put_deposit(self.requestor_sci, requestors_funds)
        self._perform_payments_scenario(LOA, requestors_funds, 0)

    def test_requestor_has_no_funds(self):
        LOA = self._prepare_list_of_acceptances()
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=LOA,
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertServiceRefused(response, sr_reasons.TooSmallRequestorDeposit)

    def test_sra_not_signed(self):
        rct = msg_factories.tasks.ReportComputedTaskFactory(
            **self.gen_rtc_kwargs(),
            **self.gen_ttc_kwargs('task_to_compute__'),
            task_to_compute__ethsig__privkey=self.requestor_priv_key,
        )
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            report_computed_task=rct,
            payment_ts=int(time.time()) - 3600*24,
        )
        sra.sig = None
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[
                sra,
            ],
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertServiceRefused(response, sr_reasons.InvalidRequest)

    def test_empty_sra(self):
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[],
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertServiceRefused(response, sr_reasons.InvalidRequest)


class RequestorPaysTest(ForcePaymentBase):
    def test_requestor_already_payed(self):
        """React to no debts

        If V is <= 0 then Concent service responds with ForcePaymentRejected
        NoUnsettledTasksFound.
        """
        LOA = self._prepare_list_of_acceptances()
        V = sum(sra.task_to_compute.price for sra in LOA)
        self.put_deposit(self.requestor_sci, V)
        tx_hash = self.requestor_sci.batch_transfer(
            payments=[
                golem_sci.structs.Payment(
                    LOA[-1].task_to_compute.provider_ethereum_address,
                    V,
                ),
            ],
            closure_time=int(time.time()),
        )
        logger.debug(
            'Batch transfer tx hash: https://etherscan.io/tx/%s',
            tx_hash,
        )
        confirmed = False
        def _on_batch(receipt: golem_sci.structs.TransactionReceipt):
            nonlocal confirmed
            self.assertTrue(receipt.status)
            confirmed = True
        self.requestor_sci.on_transaction_confirmed(tx_hash, _on_batch)
        sys.stderr.write('Waiting for confirmation %s' % (tx_hash,))
        self.retry_until_timeout(
            lambda: confirmed,
            'Batch transfer timeout',
        )
        sys.stderr.write('\n')
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=LOA,
        )
        self.assertPaymentRejected(fp, fpr_reasons.NoUnsettledTasksFound)
