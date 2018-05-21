import calendar
import functools
import logging
import time
import typing

from ethereum.utils import privtoaddr
from golem_messages import constants as msg_constants
from golem_messages import cryptography
from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem.network import history
from golem.utils import decode_hex


logger = logging.getLogger(__name__)

RESPONSE_FOR_RCT = typing.Union[
    message.tasks.RejectReportComputedTask,
    message.tasks.AckReportComputedTask,
]


def verify_task_deadline(msg: message.base.Message) -> bool:
    now_ts = calendar.timegm(time.gmtime())
    # SEE #2683 for an explanation about TOLERANCE
    TOLERANCE = msg_constants.MTD * 2
    tolerant_now_ts = now_ts - int(TOLERANCE.total_seconds())

    # Check subtask deadline
    return tolerant_now_ts <= msg.task_to_compute.compute_task_def['deadline']


def verify_message_payment_address(
        report_computed_task: message.tasks.ReportComputedTask,
        ecc: cryptography.ECCx) -> bool:
    # Prevent self payments. This check deserve its own reject_reason but also
    # it belongs ealier in the flow rather then here.
    if privtoaddr(ecc.get_privkey()) == decode_hex(
            report_computed_task.eth_account):
        logger.warning('Prevented self payment: %r', report_computed_task)
        return False
    # Prevent payments to zero address. Same as above.
    if decode_hex(report_computed_task.eth_account) == b'\x00' * 20:
        logger.warning(
            'Prevented payment to zero address: %r',
            report_computed_task,
        )
        return False
    return True


def prepare_reject_report_computed_task(task_to_compute, reason, **kwargs) \
        -> message.tasks.RejectReportComputedTask:
    logger.debug(
        'prepare_reject_report_computed_task(%r, **%r)',
        reason,
        kwargs,
    )
    reject_msg = message.tasks.RejectReportComputedTask(
        reason=reason,
        attached_task_to_compute=task_to_compute,
        **kwargs,
    )
    return reject_msg


def process_report_computed_task_no_time_check(
        msg: message.tasks.ReportComputedTask,
        ecc: cryptography.ECCx) -> RESPONSE_FOR_RCT:
    """Requestor can't reply with SubtaskTimeLimitExceeded to Concent #2682"""

    reject_reasons = message.tasks.RejectReportComputedTask.REASON

    # Check msg.task_to_compute signature
    try:
        msg.task_to_compute.verify_signature(ecc.raw_pubkey)
    except msg_exceptions.InvalidSignature:
        return prepare_reject_report_computed_task(msg.task_to_compute, None)

    if not verify_message_payment_address(report_computed_task=msg, ecc=ecc):
        return prepare_reject_report_computed_task(msg.task_to_compute, None)

    get_msg = functools.partial(
        history.MessageHistoryService.get_sync_as_message,
        task=msg.task_id,
        subtask=msg.subtask_id,
    )

    # we're checking for existence of earlier messages here to eliminate
    # the situation when a Provider sends the Requestor a `ReportComputedTask`
    # for a task that they had previously claimed un-computable

    # CannotComputeTask received
    try:
        unwanted_msg = get_msg(msg_cls='CannotComputeTask')
        return prepare_reject_report_computed_task(
            msg.task_to_compute,
            reject_reasons.GotMessageCannotComputeTask,
            cannot_compute_task=unwanted_msg,
        )
    except history.MessageNotFound:
        pass

    # TaskFailure received
    try:
        unwanted_msg = get_msg(msg_cls='TaskFailure')
        return prepare_reject_report_computed_task(
            msg.task_to_compute,
            reject_reasons.GotMessageTaskFailure,
            task_failure=unwanted_msg,
        )
    except history.MessageNotFound:
        pass

    # Verification passed, will send ACK

    return message.tasks.AckReportComputedTask(
        report_computed_task=msg
    )


def process_report_computed_task(
        msg: message.tasks.ReportComputedTask,
        ecc: cryptography.ECCx) -> RESPONSE_FOR_RCT:

    reject_reasons = message.tasks.RejectReportComputedTask.REASON

    # Check subtask deadline
    if not verify_task_deadline(msg):
        return prepare_reject_report_computed_task(
            msg.task_to_compute,
            reject_reasons.SubtaskTimeLimitExceeded,
        )

    return process_report_computed_task_no_time_check(msg=msg, ecc=ecc)
