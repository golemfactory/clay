import datetime
from functools import partial
import time

from scripts.node_integration_tests import helpers

from ..concent_base import ConcentTestPlaybook
from ...test_config_base import NodeId


class Playbook(ConcentTestPlaybook):
    force_payment_timeout = None
    force_payment_committed_timeout = None

    pre_payment_balance = None
    expected_payment = None

    payment_timeout = None

    def step_yesterday_end(self):
        print("Shutting down yesterday's nodes")
        self.next()

    def step_today_start(self):
        print("Starting today's nodes")
        self.next()

    def step_init_force_payment_timeout(self):
        print("Waiting for ForcePayment.")
        self.force_payment_timeout = (
                datetime.datetime.now() +
                datetime.timedelta(minutes=15)
        )
        self.next()

    def step_wait_force_payment(self):
        if not self.force_payment_timeout:
            self.fail("No ForcePayment timeout? ... ")

        force_payment_test, match = self.check_concent_logs(
            self.output_queues[NodeId.provider],
            outgoing=True,
            awaited_messages=['ForcePayment', ]
        )

        if force_payment_test is True:
            self.next()
            return
        elif force_payment_test is False:
            self.fail(match.group(0))

        if datetime.datetime.now() > self.force_payment_timeout:
            self.fail("ForcePayment timed out... ")

        print("Waiting for ForcePayment...")
        time.sleep(15)

    def step_init_force_payment_committed_timeout(self):
        print("Waiting for ForcePaymentCommitted.")
        self.force_payment_committed_timeout = (
                datetime.datetime.now() +
                datetime.timedelta(minutes=15)
        )
        self.next()

    def step_wait_force_payment_committed(self):
        if not self.force_payment_committed_timeout:
            self.fail("No ForcePaymentCommitted timeout? ... ")

        force_payment_test, match = self.check_concent_logs(
            self.output_queues[NodeId.provider],
            awaited_messages=['ForcePaymentCommitted', ]
        )

        if force_payment_test is True:
            self.next()
            return
        elif force_payment_test is False:
            self.fail(match.group(0))

        if datetime.datetime.now() > self.force_payment_committed_timeout:
            self.fail("ForcePaymentCommitted timed out... ")

        print("Waiting for ForcePaymentCommitted...")
        time.sleep(15)

    @staticmethod
    def _rpc_balance_to_ether(result):
        return helpers.to_ether(result.get('gnt'))

    def step_get_provider_balance(self):
        def on_success(result):
            self.pre_payment_balance = self._rpc_balance_to_ether(result)
            print("Provider initial balance: %s" % self.pre_payment_balance)
            self.next()

        return self.call(NodeId.provider, 'pay.balance', on_success=on_success)

    def step_get_provider_expected_payment(self):
        def on_success(result):
            self.expected_payment = helpers.to_ether(sum([
                int(p.get('value'))
                for p in result
                if p.get('payer') == self.nodes_keys[NodeId.requestor] and
                   p.get('subtask') in self.subtasks[NodeId.provider]
            ]))
            if not self.expected_payment:
                print("No expected payments found for the task...")
                return

            print("Expected payment: %s" % self.expected_payment)
            self.next()

        return self.call(NodeId.provider,
                         'pay.incomes', on_success=on_success)

    def step_init_payment_timeout(self):
        print("Waiting for blockchain payment.")
        self.payment_timeout = (
                datetime.datetime.now() +
                datetime.timedelta(minutes=5)
        )
        self.next()

    def step_wait_for_payment(self):
        def on_success(result):
            balance = self._rpc_balance_to_ether(result)
            required_balance = self.pre_payment_balance + self.expected_payment
            print(
                "Provider current balance: %s, required: %s" %
                (balance, required_balance)
            )
            if balance > required_balance:
                print(
                    "Too much payment received...\n"
                    "Balance - Actual: %s, Required: %s" %
                    (balance, required_balance)
                )
                self.fail()
            if balance == required_balance:
                print("Payment received! \\o/ ... total: %s GNT" % balance)
                self.next()
            else:
                if datetime.datetime.now() > self.payment_timeout:
                    self.fail("Blockchain payment timed out... ")

                time.sleep(15)

        return self.call(NodeId.provider, 'pay.balance', on_success=on_success)

    steps = ConcentTestPlaybook.initial_steps + (
        step_get_provider_balance,
        ConcentTestPlaybook.step_create_task,
        ConcentTestPlaybook.step_get_task_id,
        ConcentTestPlaybook.step_get_task_status,
        ConcentTestPlaybook.step_wait_task_finished,
        ConcentTestPlaybook.step_get_subtasks,
        step_get_provider_expected_payment,
        step_yesterday_end,
        ConcentTestPlaybook.step_stop_nodes,
        step_today_start,
        ConcentTestPlaybook.step_restart_nodes,
        partial(ConcentTestPlaybook.step_get_key, node_id=NodeId.provider),
        partial(ConcentTestPlaybook.step_get_key,
                node_id=NodeId.requestor),
        step_init_force_payment_timeout,
        step_wait_force_payment,
        step_init_force_payment_committed_timeout,
        step_wait_force_payment_committed,
        step_init_payment_timeout,
        step_wait_for_payment,
    )
