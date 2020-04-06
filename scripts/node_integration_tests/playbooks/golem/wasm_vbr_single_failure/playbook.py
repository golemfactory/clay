import time
from functools import partial

from .test_config import NodeId

from ..wasm_vbr_success.playbook import Playbook as NodeTestPlaybook


class Playbook(NodeTestPlaybook):

    REDUNDANCY_FACTOR = 1

    def step_wait_for_arbitration_required(
            self, node_id: NodeId = NodeId.requestor):
        def on_success(result):
            subtasks = {}
            if result:
                subtasks = {
                    self.nodes_keys.inverse[s['node_id']]: s.get('subtask_id')
                    for s in result
                    if s.get('status') == 'Verifying'
                }
            if subtasks and len(subtasks) == self.REDUNDANCY_FACTOR + 1:
                print("Subtasks finished. Awaiting arbitration")
                self.next()
            else:
                print("Waiting for 2 subtasks Vbr to finish")
                time.sleep(10)

        return self.call(node_id, 'comp.task.subtasks', self.task_id,
                         on_success=on_success)

    steps = NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,

        step_wait_for_arbitration_required,

        partial(NodeTestPlaybook.step_get_key, node_id=NodeId.provider3),
        partial(NodeTestPlaybook.step_configure, node_id=NodeId.provider3),
        partial(NodeTestPlaybook.step_get_network_info,
                node_id=NodeId.provider3),
        partial(NodeTestPlaybook.step_connect, node_id=NodeId.provider3,
                target_node=NodeId.requestor),
        partial(NodeTestPlaybook.step_verify_connection,
                node_id=NodeId.requestor, target_node=NodeId.provider3),

        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_get_subtasks,

        partial(NodeTestPlaybook.step_verify_income, node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_verify_income, node_id=NodeId.provider3),
    )
