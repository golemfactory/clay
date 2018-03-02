import calendar
import functools
import logging
import time

from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem.network import history
from golem.network.concent import exceptions


logger = logging.getLogger(__name__)


def process_report_computed_task(msg, task_session):
    # Check msg.task_to_compute signature
    try:
        task_session.task_server.keys_auth.ecc.verify(
            sig=msg.task_to_compute.sig,
            inputb=msg.task_to_compute.get_short_hash(),
        )
    except (AssertionError, msg_exceptions.InvalidSignature):
        logger.warning('Received fake task_to_compute: %r', msg)
        task_session.dropped()
        return

    def send_reject(reason, **kwargs):
        logger.debug(
            '_reacto_to_computed_task.send_reject(%r, **%r)',
            reason,
            kwargs,
        )
        task_session.send(message.concents.RejectReportComputedTask(
            subtask_id=msg.subtask_id,
            reason=reason,
            task_to_compute=msg.task_to_compute,
            **kwargs,
        ))

    reject_reasons = message.concents.RejectReportComputedTask.REASON
    now_ts = calendar.timegm(time.gmtime())
    task_id = msg.task_to_compute.compute_task_def['task_id']

    # Check task deadline
    if now_ts > msg.task_to_compute.compute_task_def['deadline']:
        send_reject(reject_reasons.TaskTimeLimitExceeded)
        raise exceptions.ConcentVerificationFailed("Task timeout")
    # Check subtask deadline
    try:
        subtask_deadline = \
            task_session.task_manager.tasks_states[task_id] \
                        .subtask_states[msg.subtask_id] \
                        .deadline
    except KeyError:
        logger.warning(
            'Deadline for subtask %r not found.'
            'Treating as timeouted. Message: %s',
            msg.subtask_id,
            msg,
        )
        subtask_deadline = -1

    if now_ts > subtask_deadline:
        send_reject(reject_reasons.SubtaskTimeLimitExceeded)
        raise exceptions.ConcentVerificationFailed("Subtask timeout")

    get_msg = functools.partial(
        history.MessageHistoryService.get_sync_as_message,
        task=task_id,
        subtask=msg.subtask_id,
    )

    # we're checking for existence of earlier messages here to eliminate
    # the situation when a Provider sends the Requestor a `ReportComputedTask`
    # for a task that they had previously claimed un-computable

    # CannotComputeTask received
    try:
        unwanted_msg = get_msg(msg_cls='CannotComputeTask')
        send_reject(
            reject_reasons.GotMessageCannotComputeTask,
            cannot_compute_task=unwanted_msg,
        )
        #
        # @fixme: the name `ConcentVerification` is confusing in this context
        #
        raise exceptions.ConcentVerificationFailed("CannotComputeTask received")
    except history.MessageNotFound:
        pass

    # TaskFailure received
    try:
        unwanted_msg = get_msg(msg_cls='TaskFailure')
        send_reject(
            reject_reasons.GotMessageTaskFailure,
            task_failure=unwanted_msg,
        )
        raise exceptions.ConcentVerificationFailed("TaskFailure received")
    except history.MessageNotFound:
        pass

    # Verification passed, will send ACK

    task_session.send(message.concents.AckReportComputedTask(
        subtask_id=msg.subtask_id,
        task_to_compute=msg.task_to_compute,
    ))
