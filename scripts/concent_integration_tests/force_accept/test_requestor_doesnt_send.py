# pylint: disable=protected-access,no-member
import calendar
import datetime
import logging
import random
import sys
import threading
import time
import uuid

from golem_messages import constants
from golem_messages import factories as msg_factories
from golem_messages import helpers
from golem_messages import message

from golem import testutils
from golem.network.concent import exceptions as concent_exceptions
from golem.transactions.ethereum import ethereumtransactionsystem as libets

from ..base import ConcentBaseTest


reasons = message.concents.ForceSubtaskResultsRejected.REASON
logger = logging.getLogger(__name__)
moment = datetime.timedelta(seconds=2)


class RequestorDoesntSendTestCase(ConcentBaseTest, testutils.DatabaseFixture):
    """Requestor doesn't send Ack/Reject of SubtaskResults"""
    def setUp(self):
        random.seed()
        ConcentBaseTest.setUp(self)
        testutils.DatabaseFixture.setUp(self)
        self.ets = libets.EthereumTransactionSystem(
            datadir=self.tempdir,
            node_priv_key=self.requestor_keys.raw_privkey,
        )

    def wait_for_gntb(self):
        sys.stderr.write('Waiting for GNTB...\n')
        while self.ets._gntb_balance <= 0:
            try:
                self.ets._run()
            except ValueError as e:
                # web3 will raise ValueError if 'error' is present
                # in response from geth
                sys.stderr.write('E: {}\n'.format(e))
            sys.stderr.write(
                'Still waiting. GNT: {:22} GNTB: {:22} ETH: {:17}\n'.format(
                    self.ets._gnt_balance,
                    self.ets._gntb_balance,
                    self.ets._eth_balance,
                ),
            )
            time.sleep(10)

    def requestor_put_deposit(self, price: int):
        start = datetime.datetime.now()
        self.wait_for_gntb()
        amount, _ = helpers.requestor_deposit_amount(
            # We'll use subtask price. Total number of subtasks is unknown
            price,
        )

        transaction_processed = threading.Event()

        def _callback(receipt):
            if not receipt.status:
                raise RuntimeError("Deposit failed")
            transaction_processed.set()

        self.ets.concent_deposit(
            required=amount,
            expected=amount,
            reserved=0,
            cb=_callback,
        )
        while not transaction_processed.is_set():
            sys.stderr.write('.')
            sys.stderr.flush()
            self.ets._sci._monitor_blockchain_single()
            time.sleep(15)
        sys.stderr.write("\nDeposit confirmed in {}\n".format(
            datetime.datetime.now()-start))

    def prepare_report_computed_task(self, mode, **kwargs):
        """Returns ReportComputedTask with open force acceptance window

        Can be modified by delta
        """

        report_computed_task = msg_factories.tasks.ReportComputedTaskFactory(
            **self.gen_rtc_kwargs(),
            **self.gen_ttc_kwargs(
                'task_to_compute__'),
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
        self.requestor_put_deposit(price)
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
            ack_report_computed_task__sign__privkey=self.requestor_priv_key,
            **kwargs,
            sign__privkey=self.provider_priv_key,
        )
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
        print(fsr)
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
        task_id = str(uuid.uuid1())
        subtask_id = str(uuid.uuid1())
        ctd_prefix = 'task_to_compute__' \
            'compute_task_def__'
        kwargs = {
            ctd_prefix+'task_id': task_id,
            ctd_prefix+'subtask_id': subtask_id,
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
            task_to_compute=fsr
            .ack_report_computed_task
            .report_computed_task
            .task_to_compute,
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
