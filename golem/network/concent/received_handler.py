import inspect
import logging

from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem.task import taskserver

from golem.network.concent import helpers as concent_helpers
from golem.network.concent.handlers_library import library

logger = logging.getLogger(__name__)


def handler_for(msg_cls: message.base.Message):
    def wrapped(f):
        f.handler_for = msg_cls
        return f
    return wrapped


def register_handlers(instance) -> None:
    for _, method in inspect.getmembers(instance, inspect.ismethod):
        try:
            msg_cls = method.handler_for
        except AttributeError:
            continue
        library.register_handler(msg_cls)(method)


class TaskServerMessageHandler():
    """Container for received message handlers that require TaskServer."""
    def __init__(self, task_server: taskserver.TaskServer):
        self.task_server = task_server
        register_handlers(self)

    @property
    def concent_service(self):
        return self.task_server.client.concent_service

    @handler_for(message.concents.ServiceRefused)
    def on_concents_service_refused(self, msg):
        self.task_server.concent_refused(
            subtask_id=msg.subtask_id,
            reason=msg.reason,
        )

    @handler_for(message.concents.VerdictReportComputedTask)
    def on_verdict_report_computed_task(self, msg):
        """Verdict is forced by Concent on Requestor

        Requestor should act as it had sent AckReportComputedTask by himself.
        """

        logger.warning("[CONCENT] Received verdict: %s", msg)

        # Verify TaskToCompute signature
        ttcs_tuple = (
            msg.ack_report_computed_task.task_to_compute,
            msg.force_report_computed_task.report_computed_task.task_to_compute,
        )
        for ttc in ttcs_tuple:
            try:
                self.task_server.keys_auth.ecc.verify(
                    sig=ttc.sig,
                    inputb=ttc.get_short_hash(),
                )
            except msg_exceptions.InvalidSignature:
                logger.error(
                    '[CONCENT] Received fake TaskToCompute from Concent: %s',
                    msg,
                )
                return

        # are all ttc equal?
        if not ttcs_tuple.count(ttcs_tuple[0]) == len(ttcs_tuple):
            logger.error(
                '[CONCENT] Received differing TaskToCompute'
                ' from Concent: %s',
                msg,
            )
            return

        rct = msg \
            .force_report_computed_task \
            .report_computed_task

        self.task_server.receive_subtask_computation_time(
            rct.subtask_id,
            rct.computation_time,
        )

    @handler_for(message.concents.ForceReportComputedTask)
    def on_force_report_computed_task(self, msg):
        """Concent forwarded ReportComputedTask from Provider

        Requestor should answer to Concent with either AckReportComputedTask
        or RejectReportComputedTask
        """
        rct = msg.report_computed_task

        returned_msg = concent_helpers.process_report_computed_task(
            msg=rct,
            ecc=self.task_server.keys_auth.ecc,
            task_header_keeper=self.task_server.task_keeper,
        )
        self.concent_service.submit_task_message(
            rct.subtask_id,
            returned_msg,
        )

        if isinstance(returned_msg, message.concents.RejectReportComputedTask):
            return

        self.task_server.receive_subtask_computation_time(
            rct.subtask_id,
            rct.computation_time,
        )
