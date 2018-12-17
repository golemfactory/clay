from scripts.node_integration_tests import helpers

from .concent_base import ConcentTestPlaybook


class ForceDownload(ConcentTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/fail_results'

    forced_download_successful = False

    def step_wait_task_finished(self):
        fail_triggers = ['Concent request failed', ]
        download_trigger = ['Concent results download successful', ]

        log_match_pattern = \
            '.*' + '.*|.*'.join(fail_triggers + download_trigger) + '.*'

        log_match = helpers.search_output(
            self.requestor_output_queue,
            log_match_pattern,
        )

        if log_match:
            match = log_match.group(0)
            if any([t in match for t in fail_triggers]):
                self.fail("Requestor<->Concent comms failure: %s " % match)
                return
            if any([t in match for t in download_trigger]):
                print("Concent download successful.")
                self.forced_download_successful = True

        concent_fail = helpers.search_output(
            self.provider_output_queue,
            ".*Concent request failed.*|.*Can't receive message from Concent.*",
        )

        if concent_fail:
            print("Provider: ", concent_fail.group(0))
            self.fail()
            return

        return super().step_wait_task_finished()

    def step_verify_forced_download_happened(self):
        if self.forced_download_successful:
            self.next()
        else:
            self.fail(
                "The task might have finished but "
                "we didn't notice the Requestor<->Concent communicating."
            )

    steps = ConcentTestPlaybook.initial_steps + (
        ConcentTestPlaybook.step_create_task,
        ConcentTestPlaybook.step_get_task_id,
        ConcentTestPlaybook.step_get_task_status,
        step_wait_task_finished,
        step_verify_forced_download_happened,
        ConcentTestPlaybook.step_verify_output,
        ConcentTestPlaybook.step_get_subtasks,
        ConcentTestPlaybook.step_verify_provider_income,
    )
