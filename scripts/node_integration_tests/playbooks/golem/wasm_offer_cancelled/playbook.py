from ..wasm_vbr_success.playbook import Playbook as WasmTestPlaybook


class Playbook(WasmTestPlaybook):

    REDUNDANCY_FACTOR = 1

    steps = WasmTestPlaybook.initial_steps + (

        WasmTestPlaybook.step_create_task,
        WasmTestPlaybook.step_get_task_id,
        WasmTestPlaybook.step_get_task_status,

        WasmTestPlaybook.step_wait_task_finished,

    )
