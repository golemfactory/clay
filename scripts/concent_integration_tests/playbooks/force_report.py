from scripts.concent_integration_tests import helpers
from .base import NodeTestPlaybook


class ForceReport(NodeTestPlaybook):
    provider_node_script = 'provider/impatient_frct'
    requestor_node_script = 'requestor/no_ack_rct'

    def step_clear_provider_output(self):
        helpers.clear_output(self.provider_output_queue)
        self.next()

    def step_wait_task_finished(self):
        concent_fail = helpers.search_output(
            self.provider_output_queue,
            '.*Concent request failed.*|.*Problem interpreting.*',
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
        step_clear_provider_output,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_finished,
    )
