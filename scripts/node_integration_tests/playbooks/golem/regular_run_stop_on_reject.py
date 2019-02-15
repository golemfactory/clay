import time
import typing

from scripts.node_integration_tests import helpers

from ..base import NodeTestPlaybook


class RegularRun(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/debug'

    def step_wait_task_finished(self):
        verification_rejected = helpers.search_output(
            self.provider_output_queue, '.*SubtaskResultsRejected.*'
        )

        if verification_rejected:
            self.fail(verification_rejected.group(0))
            return

        def on_success(result):
            if result['status'] == 'Finished':
                print("Task finished.")
                self.next()
            elif result['status'] == 'Timeout':
                self.fail("Task timed out :( ... ")
            else:
                print("{} ... ".format(result['status']))
                time.sleep(10)

        return self.call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
        NodeTestPlaybook.step_get_subtasks,
        NodeTestPlaybook.step_verify_provider_income,
    )
