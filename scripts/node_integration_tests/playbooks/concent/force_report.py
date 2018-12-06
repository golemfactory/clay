import datetime
import time

from scripts.node_integration_tests import helpers


from ..base import NodeTestPlaybook


class ForceReport(NodeTestPlaybook):
    provider_node_script = 'provider/impatient_frct'
    requestor_node_script = 'requestor/no_ack_rct'

    task_finished = False
    ack_rct_received = False
    ack_rct_deadline = None

    def step_clear_provider_output(self):
        helpers.clear_output(self.provider_output_queue)
        self.next()

    def step_wait_task_finished_and_arct_received(self):
        def on_success(result):
            if result['status'] == 'Finished':
                print("Task finished.")
                self.task_finished = True
                self.ack_rct_deadline = \
                    datetime.datetime.now() + datetime.timedelta(minutes=3)
            elif result['status'] == 'Timeout':
                self.fail("Task timed out :( ... ")
            else:
                print("{} ... ".format(result['status']))
                time.sleep(10)

        concent_fail_triggers = [
            'Concent request failed',
            'Problem interpreting',
        ]

        ack_rct_trigger = [
            'AckReportComputedTask'
        ]

        log_match_pattern = \
            '.*' + '.*|.*'.join(concent_fail_triggers + ack_rct_trigger) + '.*'

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
                    for t in ack_rct_trigger]):
                print("AckReportComputedTask received.")
                self.ack_rct_received = True

        if self.task_finished and self.ack_rct_received:
            print("Task finished and ARTC received, great! :)")
            self.next()
            return

        if ((not self.ack_rct_received) and
                self.ack_rct_deadline and
                datetime.datetime.now() > self.ack_rct_deadline
        ):
            self.fail("ARCT timeout...")
            return

        if not self.task_finished:
            return self.call_requestor(
                'comp.task', self.task_id,
                on_success=on_success,
                on_error=self.print_error
            )

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
        step_wait_task_finished_and_arct_received,
        NodeTestPlaybook.step_verify_output,
        NodeTestPlaybook.step_get_subtasks,
        NodeTestPlaybook.step_verify_provider_income,
    )
