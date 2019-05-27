from functools import partial
import time
import typing

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId


class Playbook(NodeTestPlaybook):
    """
    Reproduces a scenario where:
    * Requestor has a a task with 2 subtasks,
    * on the first run, the Provider is modified to respond to a task just once
      (it should send only one `WantToComputeTask`),
    * because there's just one Provider who accepts only one subtask,
      the task as a whole should time out,
    * afterwards, the nodes are restarted, this time both as unmodified
      Golem nodes,
    * the timed-out task (with only one subtask successfully finished) is then
      restarted using the `comp.task.restart_subtasks` call - the result is a
      new task which contains one already-completed subtask and another,
      failed one,
    * the Provider should then be able to pick up that second subtask, thus
      allowing the task as a whole to finish successfully this time.

    """
    previous_task_id = None

    def step_wait_subtask_completed(self):
        def on_success(result):
            if result:
                statuses = [s.get('status') for s in result]
                if 'Finished' in statuses:
                    print("First subtask finished")
                    self.next()
                elif 'Failure' in statuses:
                    print('Subtask failed :(')
                    self.fail("Got status 'Failure', expected 'Finished'.")
                else:
                    print("Subtasks status: {}".format(statuses))

            time.sleep(10)

        return self.call(NodeId.requestor, 'comp.task.subtasks', self.task_id,
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

    def step_restart_task(self):
        def on_success(result):
            print("Restarted task. {}".format(result))
            self.next()

        if not self.task_in_creation:
            print("Restarting subtasks for {}".format(self.previous_task_id))
            self.task_in_creation = True
            return self.call(NodeId.requestor, 'comp.task.restart_subtasks',
                             self.previous_task_id, [],
                             on_success=on_success)

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_subtask_completed,
        step_wait_task_timeout,
        NodeTestPlaybook.step_stop_nodes,
        NodeTestPlaybook.step_restart_nodes,
    ) + NodeTestPlaybook.initial_steps + (
        step_restart_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
    )
