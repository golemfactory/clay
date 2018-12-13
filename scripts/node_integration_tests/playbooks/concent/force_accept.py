import calendar
import datetime
import time

from golem_messages import helpers as msg_helpers
from golem_messages.factories.tasks import ReportComputedTaskFactory

from scripts.node_integration_tests import helpers

from ..base import NodeTestPlaybook


class ForceAccept(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/no_sra'

    task_finished = False
    sra_received = False
    sra_deadline = None

    @property
    def subtask_timeout_secs(self):
        return helpers.timeout_to_seconds(
            self.task_settings_dict.get('subtask_timeout'))

    def get_svt(self) -> datetime.timedelta:
        deadline = calendar.timegm(time.gmtime()) + self.subtask_timeout_secs
        fake_rct = ReportComputedTaskFactory(
            task_to_compute__compute_task_def__deadline=deadline,
            size=1000000,  # @todo add proper size read from the provider's
                           # results directory, if possible
        )
        return msg_helpers.subtask_verification_time(fake_rct)

    def step_clear_provider_output(self):
        helpers.clear_output(self.provider_output_queue)
        self.next()

    def step_wait_task_finished_and_sra_received(self):
        def on_success(result):
            if result['status'] == 'Finished':
                self.task_finished = True
                sra_delay = (self.subtask_timeout_secs +
                             self.get_svt() +
                             datetime.timedelta(minutes=3))
                print(
                    "Task finished. "
                    "Now waiting for the SRA to arrive, %s" % sra_delay
                )
                self.sra_deadline = datetime.datetime.now() + sra_delay
            elif result['status'] == 'Timeout':
                self.fail("Task timed out :( ... ")
            else:
                print("{} ... ".format(result['status']))
                time.sleep(10)

        concent_fail_triggers = [
            'Concent request failed',
            'Problem interpreting',
        ]

        sra_trigger = [
            'ForceSubtaskResultsResponse'
        ]

        log_match_pattern = \
            '.*' + '.*|.*'.join(concent_fail_triggers + sra_trigger) + '.*'

        log_match = helpers.search_output(
            self.provider_output_queue,
            log_match_pattern,
        )

        if log_match:
            match = log_match.group(0)
            if any([t in match for t in concent_fail_triggers]):
                self.fail("Provider<->Concent comms failure: %s " % match)
                return
            if any([t in match and 'Concent Message received' in match
                    for t in sra_trigger]):
                print("Forced SRA received.")
                self.sra_received = True

        if self.task_finished and self.sra_received:
            print("Task finished and the relayed SRA received, great! :)")
            self.next()
            return

        if ((not self.sra_received) and
                self.sra_deadline and
                datetime.datetime.now() > self.sra_deadline
        ):
            self.fail("Forced SRA timeout...")
            return

        if not self.task_finished:
            return self.call_requestor(
                'comp.task', self.task_id,
                on_success=on_success,
                on_error=self.print_error
            )

        if not self.sra_received:
            print("Waiting for SRA...")
            time.sleep(30)

    steps = (
        NodeTestPlaybook.step_get_provider_key,
        NodeTestPlaybook.step_get_requestor_key,
        NodeTestPlaybook.step_get_provider_network_info,
        NodeTestPlaybook.step_connect_nodes,
        NodeTestPlaybook.step_verify_peer_connection,
        NodeTestPlaybook.step_wait_provider_gnt,
        NodeTestPlaybook.step_wait_requestor_gnt,
        NodeTestPlaybook.step_get_known_tasks,
        step_clear_provider_output,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_finished_and_sra_received,
        NodeTestPlaybook.step_get_subtasks,
        NodeTestPlaybook.step_verify_provider_income,
    )
