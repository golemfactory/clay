import time
import unittest

from golem_messages import cryptography
from golem_messages import factories as msg_factories
from golem_messages import message
from golem_messages.utils import encode_hex as encode_key_id

from golem.network.concent import exceptions as concent_exceptions

from ..base import ETSBaseTest


fpr_reasons = message.concents.ForcePaymentRejected.REASON


class RquestorDoesntPayTestCase(ETSBaseTest):
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
        sra1 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            **self.gen_ttc_kwargs(
                'task_to_compute__',
            ),
            payment_ts=int(time.time()) - 3600*24,
        )
        sra1.sign_message(self.requestor_priv_key)
        sra2 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            **self.gen_ttc_kwargs(
                'task_to_compute__',
            ),
            payment_ts=int(time.time()) - 3600*24,
        )
        sra2.sign_message(self.provider_priv_key)
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[
                sra1, sra2,
            ],
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertEqual(response, message.concents.ServiceRefused)

    def test_multiple_eth_accounts(self):
        sra1 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            **self.gen_ttc_kwargs(
                'task_to_compute__',
            ),
            task_to_compute__provider_ethereum_public_key=encode_key_id(
                cryptography.ECCx(None).raw_pubkey
            ),
            payment_ts=int(time.time()) - 3600*24,
        )
        sra1.sign_message(self.requestor_priv_key)
        sra2 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            **self.gen_ttc_kwargs(
                'task_to_compute__',
            ),
            task_to_compute__provider_ethereum_public_key=encode_key_id(
                cryptography.ECCx(None).raw_pubkey
            ),
            payment_ts=int(time.time()) - 3600*24,
        )
        sra2.sign_message(self.requestor_priv_key)
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[
                sra1, sra2,
            ],
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertEqual(response, message.concents.ServiceRefused)

    def test_provider_asks_too_early(self):
        """Test messages due date

        Concent service verifies wether all messages from LAO are due.
        It responds with ForcePaymentRejected TimestampError otherwise.
        """
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            **self.gen_ttc_kwargs(
                'task_to_compute__',
            ),
            payment_ts=int(time.time()) - 100,
        )
        sra.sign_message(self.requestor_priv_key)
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[
                sra,
            ],
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertIsInstance(response, message.concents.ForcePaymentRejected)
        self.assertEqual(response.reason, fpr_reasons.TimestampError)
        self.assertEqual(response.force_payment, fp)

    @unittest.skip('too long')
    def test_no_debt(self):
        """React to no debts

        If V is <= 0 then Concent service responds with ForcePaymentRejected
        NoUnsettledTasksFound.
        """
        # REASON.NoUnsetledTasksFound
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            **self.gen_ttc_kwargs(
                'task_to_compute__',
            ),
            payment_ts=int(time.time()),
        )
        sra.sign_message(self.requestor_priv_key)
        self.requestor_put_deposit(sra.task_to_compute.price)  # noqa pylint: disable=no-member
        # TODO pay
        # TODO sleep till timeout
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[
                sra,
            ],
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertIsInstance(response, message.concents.ForcePaymentRejected)

    def test_force_payment_commited(self):
        """Concent service commits forced payment

        If deposit is higher or equal to V then V is paid to provider.
        Otherwise maximum available amount is transferred to provider.
        Both Requestor and Provider should receive ForcePaymentCommitted.
        """
        LOA = []
        for _ in range(3):
            sra = msg_factories.tasks.SubtaskResultsAcceptedFactory(
                **self.gen_ttc_kwargs(
                    'task_to_compute__',
                ),
                payment_ts=int(time.time()) - 3600*24,
            )
            sra.sign_message(self.requestor_priv_key)
            LOA.append(sra)
        V = sum(sra.task_to_compute.price for sra in LOA)
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=LOA,
        )
        response_provider = self.provider_load_response(self.provider_send(fp))
        response_requestor = self.requestor_receive_oob()
        roles = message.concents.ForcePaymentCommitted.Actor
        for response in (response_provider, response_requestor):
            self.assertIsInstance(
                response,
                message.concents.ForcePaymentCommitted,
            )
            self.assertEqual(
                response.payment_ts,
                max(sra.payment_ts for sra in LOA),
            )
            self.assertEqual(
                response.task_owner_key,
                self.requestor_pub_key,
            )
            self.assertEqual(
                response.provider_eth_account,
                LOA[0].task_to_compute.provider_ethereum_address,
            )
            self.assertEqual(
                response.amount_paid,
                0,
            )
            self.assertEqual(
                response.amount_pending,
                V,
            )
        self.assertEqual(response_provider.recipient_type, roles.Provider)
        self.assertEqual(response_requestor.recipient_type, roles.Requestor)

    def test_sra_not_signed(self):
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            **self.gen_ttc_kwargs(
                'task_to_compute__',
            ),
            payment_ts=int(time.time()) - 3600*24,
        )
        sra.sig = None
        fp = message.concents.ForcePayment(
            subtask_results_accepted_list=[
                sra,
            ],
        )
        response = self.provider_load_response(self.provider_send(fp))
        self.assertIsInstance(response, message.concents.ServiceRefused)
