import datetime
import re
import time

from golem_messages.message.tasks import AckReportComputedTask
from golem_messages.register import library

from scripts.node_integration_tests import helpers


from .concent_base import ConcentTestPlaybook


class ForceReport(ConcentTestPlaybook):
    provider_node_script = 'provider/impatient_frct'
    requestor_node_script = 'requestor/no_ack_rct'

    task_finished = False
    ack_rct_received = False
    ack_rct_deadline = None

    def step_wait_task_finished_and_arct_received(self):
        def on_success(result):
            if result['status'] == 'Finished':
                arct_delay = datetime.timedelta(minutes=3)
                print("Task finished. Now waiting for ARCT: %s" % arct_delay)
                self.task_finished = True
                self.ack_rct_deadline = \
                    datetime.datetime.now() + arct_delay
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
            'MessageHeader(type_=' + str(
                library.get_type(AckReportComputedTask)
            )
        ]

        log_match_pattern = '.*' + '.*|.*'.join([
            re.escape(t) for t in
            (concent_fail_triggers + ack_rct_trigger)
        ]) + '.*'
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
                datetime.datetime.now() > self.ack_rct_deadline):
            self.fail("ARCT timeout...")
            return

        if not self.task_finished:
            return self.call_requestor(
                'comp.task', self.task_id,
                on_success=on_success,
                on_error=self.print_error
            )

    steps = ConcentTestPlaybook.initial_steps + (
        ConcentTestPlaybook.step_create_task,
        ConcentTestPlaybook.step_get_task_id,
        ConcentTestPlaybook.step_get_task_status,
        step_wait_task_finished_and_arct_received,
        ConcentTestPlaybook.step_verify_output,
        ConcentTestPlaybook.step_get_subtasks,
        ConcentTestPlaybook.step_verify_provider_income,
    )
