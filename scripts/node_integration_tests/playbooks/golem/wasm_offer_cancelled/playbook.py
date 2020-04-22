from ...base import NodeTestPlaybook

#from ..wasm_vbr_success.playbook import Playbook as WasmTestPlaybook


class Playbook(NodeTestPlaybook):

    REDUNDANCY_FACTOR = 1

    steps = NodeTestPlaybook.initial_steps + (

        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,

        NodeTestPlaybook.step_wait_task_finished,

    )
