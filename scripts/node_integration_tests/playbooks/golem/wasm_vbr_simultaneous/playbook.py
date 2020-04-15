from ..wasm_vbr_success.playbook import Playbook as WasmTestPlaybook
from ..simultaneous_tasks.playbook import Playbook as SimultaneousTaskPlaybook


class Playbook(SimultaneousTaskPlaybook, WasmTestPlaybook):

    REDUNDANCY_FACTOR = 1

    steps = WasmTestPlaybook.initial_steps + (
        WasmTestPlaybook.step_create_task,
        WasmTestPlaybook.step_get_task_id,
        WasmTestPlaybook.step_get_task_status,

        WasmTestPlaybook.step_create_task,
        SimultaneousTaskPlaybook.step_get_task_id2,

        WasmTestPlaybook.step_wait_task_finished,
        SimultaneousTaskPlaybook.step_wait_task_finished2,

    )
