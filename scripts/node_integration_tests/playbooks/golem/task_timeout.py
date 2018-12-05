import time
import typing

from ..base import NodeTestPlaybook


class TaskTimeoutAndRestart(NodeTestPlaybook):
    provider_node_script = 'provider/no_wtct_after_ttc'
    requestor_node_script = 'requestor/debug'
    task_settings = '2_short'
    provider_node_script_2 = 'provider/debug'
    previous_task_id = None

    def step_wait_subtask_completed(self):
        def on_success(result):
            if result:
                statuses = map(lambda s: s.get('status'), result)
                if any(map(lambda s: s == 'Finished', statuses)):
                    print("First subtask finished")
                    self.next()
                    return
                print("Subtasks status: {}".format(list(statuses)))

            time.sleep(10)

        return self.call_requestor('comp.task.subtasks', self.task_id,
                              on_success=on_success, on_error=self.print_error)

    def step_wait_task_timeout(self):
        def on_success(result):
            if result['status'] == 'Timeout':
                print("Task timed out as expected.")
                self.previous_task_id = self.task_id
                self.task_id = None
                self.next()
            elif result['status'] == 'Finished':
                print(f'Task finished unexpectedly, failing test :(')
                self.fail()
            else:
                print("Task status: {} ... ".format(result['status']))
                time.sleep(10)

        return self.call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    def step_stop_nodes(self):
        if self.started:
            print("Stopping nodes")
            self.stop_nodes()

        time.sleep(10)
        provider_exit = self.provider_node.poll()
        requestor_exit = self.requestor_node.poll()
        if provider_exit is not None and requestor_exit is not None:
            if provider_exit or requestor_exit:
                print(
                    "Abnormal termination provider: %s, requestor: %s",
                    provider_exit,
                    requestor_exit,
                )
                self.fail()
            else:
                print("Stopped nodes")
                self.next()
        else:
            print("...")

    def step_restart_nodes(self):
        print("Starting nodes again")
        # replace the failing provider node with a regular one
        self.provider_node_script = self.provider_node_script_2
        self.task_in_creation = False
        time.sleep(60)

        self.start_nodes()
        print("Nodes restarted")
        self.next()

    def step_restart_task(self):
        def on_success(result):
            print("Restarted task. {}".format(result))
            self.next()

        if not self.task_in_creation:
            print("Restarting subtasks for {}".format(self.previous_task_id))
            self.task_in_creation = True
            return self.call_requestor('comp.task.restart_subtasks',
                                  self.previous_task_id, [],
                                  on_success=on_success,
                                  on_error=self.print_error)

    def step_success(self):
        self.success()

    steps: typing.Tuple = (
        NodeTestPlaybook.step_get_provider_key,
        NodeTestPlaybook.step_get_requestor_key,
        NodeTestPlaybook.step_get_provider_network_info,
        NodeTestPlaybook.step_connect_nodes,
        NodeTestPlaybook.step_verify_peer_connection,
        NodeTestPlaybook.step_wait_provider_gnt,
        NodeTestPlaybook.step_wait_requestor_gnt,
        NodeTestPlaybook.step_get_known_tasks,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_subtask_completed,
        step_wait_task_timeout,
        step_stop_nodes,
        step_restart_nodes,
        NodeTestPlaybook.step_get_provider_key,
        NodeTestPlaybook.step_get_requestor_key,
        NodeTestPlaybook.step_get_provider_network_info,
        NodeTestPlaybook.step_connect_nodes,
        NodeTestPlaybook.step_verify_peer_connection,
        NodeTestPlaybook.step_wait_provider_gnt,
        NodeTestPlaybook.step_wait_requestor_gnt,
        NodeTestPlaybook.step_get_known_tasks,
        step_restart_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
        step_success,
    )
