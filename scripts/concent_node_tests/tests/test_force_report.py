#!/usr/bin/env python
import sys
import time

from scripts.concent_node_tests import helpers
from scripts.concent_node_tests.tests.base import (
    NodeTestPlaybook, call_requestor)


class ForceReport(NodeTestPlaybook):
    provider_node_script = 'provider/impatient_frct'
    requestor_node_script = 'requestor/no_ack_rct'

    def step_clear_provider_output(self):
        helpers.clear_output(self.provider_output_queue)
        self.next()

    def step_wait_task_finished(self):
        provider_concent_fail = helpers.search_output(
            self.provider_output_queue,
            '.*Concent request failed.*',
        )

        if provider_concent_fail:
            print("Provider: ", provider_concent_fail.group(0))
            self.fail()
            return

        def on_success(result):
            if result['status'] == 'Finished':
                print("Task finished.")
                self.success()
            else:
                print("{} ... ".format(result['status']))
                time.sleep(5)

        call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    steps = (
        NodeTestPlaybook.step_get_provider_key,
        NodeTestPlaybook.step_get_requestor_key,
        NodeTestPlaybook.step_get_provider_network_info,
        NodeTestPlaybook.step_connect_nodes,
        NodeTestPlaybook.step_verify_peer_connection,
        NodeTestPlaybook.step_get_known_tasks,
        step_clear_provider_output,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_finished,
    )


playbook = ForceReport.start()
if playbook.exit_code:
    print("exit code", playbook.exit_code)
sys.exit(playbook.exit_code)
