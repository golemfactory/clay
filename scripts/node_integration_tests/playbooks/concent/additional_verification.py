import time

from scripts.node_integration_tests import helpers

from ..base import NodeTestPlaybook


class AdditionalVerification(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/reject_results'

    def step_clear_provider_output(self):
        helpers.clear_output(self.provider_output_queue)
        self.next()

    def step_wait_task_started(self):
        def on_success(result):
            if result['status'] == 'Waiting':
                print("Task started.")
                self.next()
            elif result['status'] == 'Timeout':
                self.fail("Task timed out :( ... ")
            else:
                print("{} ... ".format(result['status']))
                time.sleep(10)

        return self.call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    def step_wait_task_rejected(self):
        sra = "SubtaskResultsAccepted"
        srr = "SubtaskResultsRejected"
        verification_received = helpers.search_output(
            self.provider_output_queue,
            '.*' + sra + '.*|.*' + srr + '.*',
        )

        if verification_received:
            verification_match = verification_received.group(0)
            if self.task_id in verification_match:
                if sra in verification_match:
                    self.fail('Results unexpectedly accepted.')
                    return
                if srr in verification_match:
                    print("Results rejected as expected.")
                    self.next()
                    return

        print("...")
        time.sleep(10)

    def step_wait(self):
        concent_fail = helpers.search_output(
            self.provider_output_queue,
            '.*Concent service exception.*',
        )

        if concent_fail:
            print("Provider: ", concent_fail.group(0))
            self.fail()
            return

    steps = NodeTestPlaybook.initial_steps + (
        step_clear_provider_output,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_started,
        step_wait_task_rejected,
        step_wait,

        # @TODO something here
        # ...?
        # profit!

    )
