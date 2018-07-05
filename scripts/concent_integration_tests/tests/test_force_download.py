#!/usr/bin/env python
import sys

from scripts.concent_integration_tests import helpers
from scripts.concent_integration_tests.tests.base import NodeTestPlaybook


class ForceDownload(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/fail_results'

    def step_clear_requestor_output(self):
        helpers.clear_output(self.requestor_output_queue)
        self.next()

    def step_clear_provider_output(self):
        helpers.clear_output(self.provider_output_queue)
        self.next()

    def step_wait_task_finished(self):
        concent_fail = helpers.search_output(
            self.requestor_output_queue,
            '.*Concent request failed.*',
        )

        if concent_fail:
            print("Requestor: ", concent_fail.group(0))
            self.fail()
            return

        concent_fail = helpers.search_output(
            self.provider_output_queue,
            ".*Concent request failed.*|.*Can't receive message from Concent.*",
        )

        if concent_fail:
            print("Provider: ", concent_fail.group(0))
            self.fail()
            return

        super().step_wait_task_finished()

    steps = (
        NodeTestPlaybook.step_get_provider_key,
        NodeTestPlaybook.step_get_requestor_key,
        NodeTestPlaybook.step_get_provider_network_info,
        NodeTestPlaybook.step_connect_nodes,
        NodeTestPlaybook.step_verify_peer_connection,
        NodeTestPlaybook.step_wait_provider_gnt,
        NodeTestPlaybook.step_wait_requestor_gnt,
        NodeTestPlaybook.step_get_known_tasks,
        step_clear_requestor_output,
        step_clear_provider_output,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_finished,
    )


playbook = ForceDownload.start()
if playbook.exit_code:
    print("exit code", playbook.exit_code)
sys.exit(playbook.exit_code)
