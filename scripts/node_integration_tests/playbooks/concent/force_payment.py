#!/usr/bin/env python
import datetime
import time

from scripts.node_integration_tests import helpers

from .concent_base import ConcentTestPlaybook


class ForcePayment(ConcentTestPlaybook):
    provider_node_script = 'provider/day_backwards'
    requestor_node_script = 'requestor/day_backwards_dont_pay'

    provider_node_script_2 = 'provider/debug'
    requestor_node_script_2 = 'requestor/dont_pay'

    force_payment_timeout = None
    force_payment_committed_timeout = None

    def step_yesterday_end(self):
        print("Shutting down yesterday's nodes")
        self.next()

    def step_today_start(self):
        print("Starting today's nodes")
        self.next()

    def step_wait_task_finished(self):
        def on_success(result):
            if result['status'] == 'Finished':
                print("Task finished.")
                self.next()
            else:
                print("{} ... ".format(result['status']))
                time.sleep(10)

        self.call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    def step_init_force_payment_timeout(self):
        self.force_payment_timeout = (
                datetime.datetime.now() +
                datetime.timedelta(minutes=15)
        )

    def step_wait_force_payment(self):
        if not self.force_payment_timeout:
            self.fail("No ForcePayment timeout? ... ")

        force_payment_test, match = self.check_concent_logs(
            self.provider_output_queue,
            awaited_messages=['ForcePayment', ]
        )

        if force_payment_test is True:
            print(match.group(0))
            self.next()
        elif force_payment_test is False:
            print(match.group(0))
            self.fail()

        if datetime.datetime.now() > self.force_payment_timeout:
            self.fail("ForcePayment timed out... ")

        print("Waiting for ForcePayment...")
        time.sleep(15)

    def step_init_force_payment_committed_timeout(self):
        self.force_payment_committed_timeout = (
                datetime.datetime.now() +
                datetime.timedelta(minutes=15)
        )

    def step_wait_force_payment_committed(self):
        if not self.force_payment_committed_timeout:
            self.fail("No ForcePaymentCommitted timeout? ... ")

        force_payment_test, match = self.check_concent_logs(
            self.provider_output_queue,
            awaited_messages=['ForcePaymentCommitted', ]
        )

        if force_payment_test is True:
            print(match.group(0))
            self.success()
        elif force_payment_test is False:
            print(match.group(0))
            self.fail()

        if datetime.datetime.now() > self.force_payment_committed_timeout:
            self.fail("ForcePaymentCommitted timed out... ")

        print("Waiting for ForcePaymentCommitted...")
        time.sleep(15)

    steps = ConcentTestPlaybook.initial_steps + (
        ConcentTestPlaybook.step_create_task,
        ConcentTestPlaybook.step_get_task_id,
        ConcentTestPlaybook.step_get_task_status,
        step_wait_task_finished,
        step_yesterday_end,
        ConcentTestPlaybook.step_stop_nodes,
        step_today_start,
        ConcentTestPlaybook.step_restart_nodes,
        ConcentTestPlaybook.step_get_provider_key,
        ConcentTestPlaybook.step_get_requestor_key,
        step_init_force_payment_timeout,
        step_wait_force_payment,
        step_init_force_payment_committed_timeout,
        step_wait_force_payment_committed,
    )
