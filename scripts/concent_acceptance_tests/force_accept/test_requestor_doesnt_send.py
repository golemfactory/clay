# pylint: disable=protected-access,no-member
import calendar
import datetime
import logging
import random
import uuid

from golem_messages import constants
from golem_messages import factories as msg_factories
from golem_messages import helpers
from golem_messages import message
from golem_messages.factories.helpers import fake_golem_uuid

from golem.network.concent import exceptions as concent_exceptions

from ..base import SCIBaseTest


reasons = message.concents.ForceSubtaskResultsRejected.REASON
logger = logging.getLogger(__name__)
moment = datetime.timedelta(seconds=2)


class RequestorDoesntSendTestCase(SCIBaseTest):
    """Requestor doesn't send Ack/Reject of SubtaskResults"""

    def prepare_report_computed_task(self, mode, **kwargs):
        """Returns ReportComputedTask with open force acceptance window

        Can be modified by delta
        """

        report_computed_task = msg_factories.tasks.ReportComputedTaskFactory(
            **self.gen_rtc_kwargs(),
            **self.gen_ttc_kwargs('task_to_compute__'),
            **kwargs,
        )
        # Difference between timestamp and deadline has to be constant
        # because it's part of SVT formula
        deadline_delta = 3600
        deadline_timedelta = datetime.timedelta(seconds=deadline_delta)
        report_computed_task.task_to_compute.compute_task_def['deadline'] = \
            report_computed_task.task_to_compute.timestamp + deadline_delta
        svt = helpers.subtask_verification_time(report_computed_task)
        now = datetime.datetime.utcnow()
        if mode == 'before':
            # We're one moment before window opens
            ttc_dt = now - deadline_timedelta - svt + moment
        elif mode == 'after':
            # We're one moment after window closed
            ttc_dt = now - deadline_timedelta - svt - constants.FAT - moment
        else:
            # We're a the beginning of the window (moment after to be sure)
            ttc_dt = now - deadline_timedelta - svt - moment
        ttc_timestamp = calendar.timegm(ttc_dt.utctimetuple())

        msg_factories.helpers.override_timestamp(
            msg=report_computed_task.task_to_compute,
            timestamp=ttc_timestamp,
        )
        report_computed_task.task_to_compute.compute_task_def['deadline'] = \
            report_computed_task.task_to_compute.timestamp + deadline_delta
        # Sign again after timestamp modification
        report_computed_task.task_to_compute.sig = None
        report_computed_task.sig = None
        report_computed_task.task_to_compute.sign_message(
            self.requestor_priv_key,
        )
        report_computed_task.sign_message(self.provider_priv_key)
        self.assertTrue(
            report_computed_task.verify_owners(
                provider_public_key=self.provider_pub_key,
                requestor_public_key=self.requestor_pub_key,
                concent_public_key=self.variant['pubkey'],
            ),
        )
        print('*'*80)
        print('TTC:', ttc_dt)
        print('WINDOW: {} ---------- {}'.format(
            ttc_dt+deadline_timedelta+svt,
            ttc_dt+deadline_timedelta+svt+constants.FAT,
        ))
        print('NOW:', now)
        print('*'*80)
        return report_computed_task

    def provider_send_force(
            self, mode='within', rct_kwargs=None, **kwargs):
        if rct_kwargs is None:
            rct_kwargs = {}
        price = random.randint(1 << 20, 10 << 20)
        self.requestor_put_deposit(helpers.requestor_deposit_amount(price)[0])
        rct_kwargs['task_to_compute__price'] = price
        report_computed_task = self.prepare_report_computed_task(
            mode=mode,
            **rct_kwargs,
        )
        fsr = msg_factories.concents.ForceSubtaskResultsFactory(
            ack_report_computed_task__report_computed_task=report_computed_task,
            **self.gen_rtc_kwargs(
                'ack_report_computed_task__'
                'report_computed_task__'),
            **self.gen_ttc_kwargs(
                'ack_report_computed_task__'
                'report_computed_task__'
                'task_to_compute__'),
            **kwargs,
        )
        fsr.task_to_compute.generate_ethsig(private_key=self.requestor_priv_key)
        fsr.task_to_compute.sign_message(
            private_key=self.requestor_priv_key,
        )
        fsr.ack_report_computed_task.report_computed_task.sign_message(
            private_key=self.provider_priv_key,
        )
        fsr.ack_report_computed_task.sign_message(
            private_key=self.requestor_priv_key,
        )
        fsr.sign_message(private_key=self.provider_priv_key)
        self.assertTrue(fsr.task_to_compute.verify_ethsig())
        self.assertEqual(fsr.task_to_compute.price, price)
        self.assertTrue(
            fsr.validate_ownership_chain(
                concent_public_key=self.variant['pubkey'],
            ),
        )
        self.assertTrue(
            fsr.verify_owners(
                provider_public_key=self.provider_keys.raw_pubkey,
                requestor_public_key=self.requestor_keys.raw_pubkey,
                concent_public_key=self.variant['pubkey'],
            ),
        )
        fsr.sig = None  # Will be signed in send_to_concent()
        response = self.provider_load_response(self.provider_send(fsr))
        self.assertIn(
            type(response),
            [
                type(None),
                message.concents.ServiceRefused,
                message.concents.ForceSubtaskResultsRejected,
            ],
        )
        return response

    def test_provider_insufficient_funds(self):
        # TODO implement when we actually implement
        # the Concent communication fee
        # Concent should immidiately respond with MessageServiceRefused
        pass

    def test_provider_before_start(self):
        response = self.provider_send_force(mode='before')
        self.assertIsInstance(
            response,
            message.concents.ForceSubtaskResultsRejected,
        )
        self.assertIs(
            response.reason,
            reasons.RequestPremature,
        )

    def test_provider_after_deadline(self):
        response = self.provider_send_force(mode='after')
        self.assertIsInstance(
            response,
            message.concents.ForceSubtaskResultsRejected,
        )
        self.assertIs(
            response.reason,
            reasons.RequestTooLate,
        )

    def test_already_processed(self):
        requestor_id = "1234"
        task_id = fake_golem_uuid(requestor_id)
        subtask_id = fake_golem_uuid(requestor_id)
        kwargs = {
            'task_to_compute__requestor_id': requestor_id,
            'task_to_compute__task_id': task_id,
            'task_to_compute__subtask_id': subtask_id,
        }
        self.assertIsNone(self.provider_send_force(rct_kwargs=kwargs))
        second_response = self.provider_send_force(rct_kwargs=kwargs)
        self.assertIsInstance(second_response, message.concents.ServiceRefused)

    def test_no_response_from_requestor(self):
        # No test, because of long sleep.
        pass

    def test_requestor_responds_with_invalid_accept(self):
        self.assertIsNone(self.provider_send_force())
        fsrr = msg_factories.concents.ForceSubtaskResultsResponseFactory()
        fsrr.subtask_results_rejected = None
        with self.assertRaises(concent_exceptions.ConcentRequestError):
            self.requestor_send(fsrr)

    def test_requestor_responds_with_invalid_reject(self):
        self.assertIsNone(self.provider_send_force())
        fsrr = msg_factories.concents.ForceSubtaskResultsResponseFactory()
        fsrr.subtask_results_accepted = None
        with self.assertRaises(concent_exceptions.ConcentRequestError):
            self.requestor_send(fsrr)

    def test_requestor_responds_with_accept(self):
        self.assertIsNone(self.provider_send_force())
        fsr = self.requestor_receive()
        self.assertTrue(
            fsr.verify_owners(
                provider_public_key=self.provider_pub_key,
                requestor_public_key=self.requestor_pub_key,
                concent_public_key=self.variant['pubkey'],
            ),
        )
        accept_msg = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            report_computed_task=fsr
            .ack_report_computed_task
            .report_computed_task,
        )
        accept_msg.sign_message(self.requestor_priv_key)
        self.assertTrue(
            accept_msg.verify_owners(
                provider_public_key=self.provider_pub_key,
                requestor_public_key=self.requestor_pub_key,
                concent_public_key=self.variant['pubkey'],
            ),
        )
        fsrr = message.concents.ForceSubtaskResultsResponse(
            subtask_results_accepted=accept_msg,
        )
        self.requestor_send(fsrr)
        received = self.provider_receive()
        self.assertIsInstance(
            received,
            message.concents.ForceSubtaskResultsResponse,
        )
        self.assertIsNone(received.subtask_results_rejected)
        self.assertEqual(received.subtask_results_accepted, accept_msg)

    def test_requestor_responds_with_reject(self):
        self.assertIsNone(self.provider_send_force())
        fsr = self.requestor_receive()
        self.assertTrue(
            fsr.verify_owners(
                provider_public_key=self.provider_pub_key,
                requestor_public_key=self.requestor_pub_key,
                concent_public_key=self.variant['pubkey'],
            ),
        )
        reject_msg = msg_factories.tasks.SubtaskResultsRejectedFactory(
            report_computed_task=fsr
            .ack_report_computed_task
            .report_computed_task
        )
        reject_msg.sign_message(self.requestor_priv_key)
        self.assertTrue(
            reject_msg.verify_owners(
                provider_public_key=self.provider_pub_key,
                requestor_public_key=self.requestor_pub_key,
                concent_public_key=self.variant['pubkey'],
            ),
        )
        fsrr = message.concents.ForceSubtaskResultsResponse(
            subtask_results_rejected=reject_msg,
        )
        self.requestor_send(fsrr)
        received = self.provider_receive()
        self.assertIsInstance(
            received,
            message.concents.ForceSubtaskResultsResponse,
        )
        self.assertIsNone(received.subtask_results_accepted)
        self.assertEqual(received.subtask_results_rejected, reject_msg)
