import calendar
import functools
import logging
import time
import typing

from golem_messages import cryptography
from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem.network import history
from golem.task import taskkeeper


logger = logging.getLogger(__name__)

RESPONSE_FOR_RCT = typing.Union[
    message.concents.RejectReportComputedTask,
    message.concents.AckReportComputedTask,
]


def process_report_computed_task(
        msg: message.tasks.ReportComputedTask,
        ecc: cryptography.ECCx,
        task_header_keeper: taskkeeper.TaskHeaderKeeper) -> RESPONSE_FOR_RCT:
    def _reject(reason, **kwargs):
        logger.debug(
            '_react_to_computed_task._reject(%r, **%r)',
            reason,
            kwargs,
        )
        reject_msg = message.concents.RejectReportComputedTask(
            subtask_id=msg.subtask_id,
            reason=reason,
            task_to_compute=msg.task_to_compute,
            **kwargs,
        )
        return reject_msg

    # Check msg.task_to_compute signature
    try:
        ecc.verify(
            sig=msg.task_to_compute.sig,
            inputb=msg.task_to_compute.get_short_hash(),
        )
    except msg_exceptions.InvalidSignature:
        logger.warning('Received fake task_to_compute: %r', msg)
        return _reject(None)

    reject_reasons = message.concents.RejectReportComputedTask.REASON
    now_ts = calendar.timegm(time.gmtime())
    task_id = msg.task_to_compute.compute_task_def['task_id']

    # Check task deadline
    try:
        task_header = task_header_keeper.task_headers[task_id]
        task_deadline = task_header.deadline
    except KeyError:
        logger.info(
            "TaskHeader for %r not found. Assuming infinite timeout.",
            task_id,
        )
        task_deadline = float('infinity')
    if now_ts > task_deadline:
        return _reject(reject_reasons.TaskTimeLimitExceeded)

    # Check subtask deadline
    if now_ts > msg.task_to_compute.compute_task_def['deadline']:
        return _reject(reject_reasons.SubtaskTimeLimitExceeded)

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
        return _reject(
            reject_reasons.GotMessageCannotComputeTask,
            cannot_compute_task=unwanted_msg,
        )
    except history.MessageNotFound:
        pass

    # TaskFailure received
    try:
        unwanted_msg = get_msg(msg_cls='TaskFailure')
        return _reject(
            reject_reasons.GotMessageTaskFailure,
            task_failure=unwanted_msg,
        )
    except history.MessageNotFound:
        pass

    # Verification passed, will send ACK

    return message.concents.AckReportComputedTask(
        subtask_id=msg.subtask_id,
        task_to_compute=msg.task_to_compute,
    )
