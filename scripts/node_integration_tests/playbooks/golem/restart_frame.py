import typing

from ..base import NodeTestPlaybook


class RestartFrame(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/debug'
    requestor_node_script_2 = 'requestor/always_accept_provider'
    task_settings = 'default'

    def step_restart_task_frame(self):
        def on_success(result):
            print(f'Restarted frame from task: {self.task_id}.')
            self.next()

        return self.call_requestor('comp.task.subtasks.frame.restart',
                                   self.task_id,
                                   '1',
                                   on_success=on_success,
                                   on_error=self.print_error)

    def step_success(self):
        self.success()

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
            step_success,
        )
