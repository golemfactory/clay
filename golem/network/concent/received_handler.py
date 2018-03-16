import inspect
import logging

from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem.model import Actor
from golem.network import history
from golem.network.concent import helpers as concent_helpers
from golem.network.concent.handlers_library import library
from golem.task import taskserver

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


@library.register_handler(message.concents.ForceReportComputedTaskResponse)
def on_force_report_computed_task_response(msg):
    """Concents response to Provider to his ForceReportComputedTask
    """
    if msg.reject_report_computed_task:
        node_id = msg.reject_report_computed_task.task_to_compute.requestor_id
    elif msg.ack_report_computed_task:
        node_id = msg.ack_report_computed_task.task_to_compute.requestor_id
    else:
        logger.warning("Can't determine node_id from %r. Assuming None", msg)
        node_id = None

    history.add(
        msg=msg,
        node_id=node_id,
        local_role=Actor.Provider,
        remote_role=Actor.Concent,
    )
    reasons = message.concents.ForceReportComputedTaskResponse.REASON

    if msg.reason == reasons.SubtaskTimeout:
        # Is reject_report_computed_task created and attached by concent?
        logger.warning("[CONCENT] SubtaskTimeout for subtask: %r", msg)
        return

    if msg.reason in (reasons.ConcentAck, reasons.AckFromRequestor):
        logger.warning(
            "[CONCENT] %s for subtask: %r",
            msg.reason,
            msg.subtask_id,
        )
        if msg.reason == reasons.ConcentAck:
            remote_role = Actor.Concent
        else:
            remote_role = Actor.Requestor
        history.add(
            msg=msg.ack_report_computed_task,
            node_id=node_id,
            local_role=Actor.Provider,
            remote_role=remote_role,
        )
        return

    if msg.reason == reasons.RejectFromRequestor:
        logger.warning(
            "[CONCENT] Reject for subtask: %r",
            msg.subtask_id,
        )
        history.add(
            msg=msg.reject_report_computed_task,
            node_id=node_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )
        return

    raise RuntimeError("Impossible condition caused by {}".format(msg))


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

    @handler_for(message.concents.ForceGetTaskResultFailed)
    def on_force_get_task_result_failed(self, msg):
        """
        Concent acknowledges a failure to retrieve the task results from
        the Provider.

        The only thing we can do at this moment is to mark the task as failed
        and preserve this message for possible later usage in case the
        Provider demands payment or tries to force acceptance.
        """

        history.add(
            msg,
            node_id=msg.task_to_compute.provider_id,
            local_role=Actor.Requestor,
            remote_role=Actor.Concent,
            sync=True,
        )

        self.task_server.task_manager.task_computation_failure(
            msg.subtask_id,
            'Error downloading the task result through the Concent'
        )

    @handler_for(message.concents.ForceSubtaskResultsResponse)
    def on_force_subtask_results_response(self, msg):
        """Concent forwards verified Requestors response to ForceSubtaskResults
        """
        if msg.subtask_results_accepted:
            node_id = msg.subtask_results_accepted.task_to_compute.requestor_id
            sub_msg = msg.subtask_results_accepted
            self.task_server.subtask_accepted(
                subtask_id=msg.subtask_id,
                accepted_ts=msg.subtask_results_accepted.payment_ts,
            )
        elif msg.subtask_results_rejected:
            node_id = msg.subtask_results_rejected \
                .report_computed_task \
                .task_to_compute.requestor_id
            sub_msg = msg.subtask_results_rejected
            self.task_server.subtask_rejected(
                subtask_id=msg.subtask_id,
            )
        else:
            raise RuntimeError("Impossible condition caused by {}".format(msg))

        history.add(
            msg=sub_msg,
            node_id=node_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )
