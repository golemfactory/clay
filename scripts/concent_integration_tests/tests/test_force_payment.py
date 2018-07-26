#!/usr/bin/env python
import sys
import time

from scripts.concent_integration_tests import helpers
from scripts.concent_integration_tests.tests.base import NodeTestPlaybook
from scripts.concent_integration_tests.rpc.client import call_requestor


class ForcePayment(NodeTestPlaybook):
    provider_node_script = 'provider/day_backwards'
    requestor_node_script = 'requestor/day_backwards_dont_pay'

    def step_shut_down_nodes(self):
        print("Shutting down yesterday's nodes")
        self.stop_nodes()
        self.next()

    def step_start_new_nodes(self):
        print("Starting today's nodes")
        self.provider_node_script = 'provider/debug'
        self.requestor_node_script = 'requestor/dont_pay'
        self.start_nodes()
        self.next()

    def step_wait_task_finished(self):
        def on_success(result):
            if result['status'] == 'Finished':
                print("Task finished.")
                self.next()
            else:
                print("{} ... ".format(result['status']))
                time.sleep(10)

        call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    def step_wait_force_payment(self):
        force_payment = helpers.search_output(
            self.provider_output_queue,
            '.*ForcePayment.*',
        )
        if force_payment:
            print(force_payment)
            self.next()
        else:
            time.sleep(20)

    steps = (
        NodeTestPlaybook.step_get_provider_key,
        NodeTestPlaybook.step_get_requestor_key,
        NodeTestPlaybook.step_get_provider_network_info,
        NodeTestPlaybook.step_connect_nodes,
        NodeTestPlaybook.step_verify_peer_connection,
        NodeTestPlaybook.step_wait_provider_gnt,
        NodeTestPlaybook.step_wait_requestor_gnt,
        NodeTestPlaybook.step_get_known_tasks,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_finished,
        step_shut_down_nodes,
        step_start_new_nodes,
        NodeTestPlaybook.step_get_provider_key,
        NodeTestPlaybook.step_get_requestor_key,
        NodeTestPlaybook.step_get_provider_network_info,
        NodeTestPlaybook.step_connect_nodes,
        NodeTestPlaybook.step_verify_peer_connection,
        step_wait_force_payment,
    )


playbook = ForcePayment.start()
if playbook.exit_code:
    print("exit code", playbook.exit_code)

sys.exit(playbook.exit_code)
