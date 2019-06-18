import time
import typing

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId


class Playbook(NodeTestPlaybook):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous_task_id = None

    def step_restart_failed_subtasks(self):
        def on_success(result):
            print(f'Restarted failed subtasks.'
                  f'task_id={self.previous_task_id}.')
            self.next()

        return self.call(NodeId.requestor,
                         'comp.task.subtasks.restart',
                         self.previous_task_id,
                         [],
                         on_success=on_success)

    def step_wait_task_timeout(self):
        def on_success(result):
            if result['status'] == 'Timeout':
                print("Task timed out as expected.")
                self.previous_task_id = self.task_id
                self.task_id = None
                self.next()
            elif result['status'] == 'Finished':
                print("Task finished unexpectedly, failing test :(")
                self.fail()
            else:
                print("Task status: {} ... ".format(result['status']))
                time.sleep(10)

        return self.call(NodeId.requestor, 'comp.task', self.task_id,
                         on_success=on_success)

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_timeout,
        NodeTestPlaybook.step_stop_nodes,
        NodeTestPlaybook.step_restart_nodes,
    ) + NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_get_known_tasks,
        step_restart_failed_subtasks,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
    )
