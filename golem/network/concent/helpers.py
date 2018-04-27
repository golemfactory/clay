import calendar
import functools
import logging
import time
import typing

from ethereum.utils import privtoaddr
from golem_messages import cryptography
from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem.network import history
from golem.task import taskkeeper
from golem.utils import decode_hex


logger = logging.getLogger(__name__)

RESPONSE_FOR_RCT = typing.Union[
    message.tasks.RejectReportComputedTask,
    message.tasks.AckReportComputedTask,
]


def verify_message_signature(
        msg: message.base.Message, ecc: cryptography.ECCx) -> bool:
    """
    Verifies that the message's signature belongs to the owner of the
    specified key pair

    :param msg: the Message to verify
    :param ecc: the `ECCx` of the alleged owner
    :return: `True` if the signature belongs to the same entity as the ecc
             `False` otherwise
    """
    try:
        ecc.verify(
            sig=msg.sig,
            inputb=msg.get_short_hash(),
        )
    except msg_exceptions.InvalidSignature:
        logger.warning('Message signature mismatch: %r', msg)
        return False

    return True


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
        reject_msg = message.tasks.RejectReportComputedTask(
            reason=reason,
            attached_task_to_compute=msg.task_to_compute,
            **kwargs,
        )
        return reject_msg

    # Check msg.task_to_compute signature
    if not verify_message_signature(msg.task_to_compute, ecc):
        return _reject(None)

    # Prevent self payments. This check deserve its own reject_reason but also
    # it belongs ealier in the flow rather then here.
    if privtoaddr(ecc.get_privkey()) == decode_hex(msg.eth_account):
        logger.warning('Prevented self payment: %r', msg)
        return _reject(None)
    # Prevent payments to zero address. Same as above.
    if decode_hex(msg.eth_account) == b'\x00' * 20:
        logger.warning('Prevented payment to zero address: %r', msg)
        return _reject(None)

    reject_reasons = message.tasks.RejectReportComputedTask.REASON
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

    return message.tasks.AckReportComputedTask(
        report_computed_task=msg
    )
