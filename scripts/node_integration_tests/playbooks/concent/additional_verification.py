import datetime
import time

from scripts.node_integration_tests import helpers

from ..base import NodeTestPlaybook


class AdditionalVerification(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/reject_results'
    concent_verification_timeout = None

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

                    #
                    # putting some arbitrary value here,
                    # @todo make the value something more sensible
                    #
                    self.concent_verification_timeout = (
                            datetime.datetime.now() +
                            datetime.timedelta(minutes=15)
                    )

                    self.next()
                    return
        else:
            def on_success(result):
                if result['status'] == 'Timeout':
                    self.fail("Task timed out without either "
                              "an acceptance or rejection...")
                else:
                    print("{} ... ".format(result['status']))
                    time.sleep(10)

            return self.call_requestor('comp.task', self.task_id,
                           on_success=on_success, on_error=self.print_error)

    def step_wait_settled(self):
        if not self.concent_verification_timeout:
            self.fail("No Concent verification timeout? ... ")

        fail_triggers = [
            "Concent request failed",
            "Can't receive message from Concent",
            "Concent service exception",
            # "SubtaskResultsRejected",
            # @todo need to add some additional condition
            # so as not to catch the original SRR
            # and only catch the Concent's one
        ]

        settled_trigger = [
            "SubtaskResultsSettled",
        ]

        log_match_pattern = \
            '.*' + '.*|.*'.join(fail_triggers + settled_trigger) + '.*'

        log_match = helpers.search_output(
            self.provider_output_queue,
            log_match_pattern,
        )

        if log_match:
            match = log_match.group(0)
            if any([t in match for t in fail_triggers]):
                self.fail(
                    "Provider's Additional Verification failed: %s " % match
                )
                return
            if any([t in match for t in settled_trigger]):
                print("Concent verification successful.")
                self.success()
                return

        if datetime.datetime.now() > self.concent_verification_timeout:
            self.fail("Concent verification timed out... ")

    steps = NodeTestPlaybook.initial_steps + (
        step_clear_provider_output,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_started,
        step_wait_task_rejected,
        step_wait_settled,

        # @todo add some concent payment check here

    )
