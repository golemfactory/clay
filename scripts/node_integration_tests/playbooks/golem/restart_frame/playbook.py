from functools import partial
import typing

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId


class Playbook(NodeTestPlaybook):
    def step_restart_task_frame(self):
        def on_success(result):
            print(f'Restarted frame from task: {self.task_id}.')
            self.next()

        return self.call(NodeId.requestor,
                         'comp.task.subtasks.frame.restart',
                         self.task_id,
                         '1',
                         on_success=on_success)

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_stop_nodes,
        NodeTestPlaybook.step_restart_nodes,
    ) + NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_get_known_tasks,
        step_restart_task_frame,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
    )
