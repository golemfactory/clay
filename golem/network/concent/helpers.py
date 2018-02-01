import calendar
import functools
import hashlib
import logging
import pathlib
import time

from golem_messages import exceptions as msg_exceptions
from golem_messages import message
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import threads

from golem.network import history
from golem.network.concent import exceptions
from golem.task import taskbase


logger = logging.getLogger(__name__)


def compute_result_hash(task_result):
    result_hash = hashlib.sha1()
    if task_result.result_type == taskbase.ResultType.FILES:
        # task_result.result is an array of filenames
        for filename in task_result.result:
            p = pathlib.Path(filename)
            logger.info(
                'Computing checksum (%.3fMB) of %s',
                p.stat().st_size / 2**20,
                p
            )
            with open(filename, 'rb') as f:
                while True:
                    chunk = f.read(2**20)  # 1MB
                    if not chunk:
                        break
                    result_hash.update(chunk)

    else:
        logger.info('Computing checksum of single result')
        result_hash.update(task_result.result.encode('utf-8'))
    return result_hash


def deferred_compute_result_hash(task_result):
    if reactor.running:
        execute = threads.deferToThread
    else:
        logger.debug('Reactor not running. Switching to blocking call')
        execute = defer.execute
    return execute(compute_result_hash, task_result)


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

    # CannotComputeTask received
    try:
        unwanted_msg = get_msg(msg_cls='CannotComputeTask')
        send_reject(
            reject_reasons.GotMessageCannotComputeTask,
            cannot_compute_task=unwanted_msg,
        )
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
