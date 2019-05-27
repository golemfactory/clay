import logging
import typing

from golem_messages import message
from golem_messages import helpers as msg_helpers
from golem_messages import utils as msg_utils

from golem import model
from golem.core import common
from golem.network import history
from golem.network.transport import msg_queue

if typing.TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem.network.p2p.local_node import LocalNode

logger = logging.getLogger(__name__)


def computed_task_reported(
        task_server,
        report_computed_task,
        after_success=lambda: None,
        after_error=lambda: None):
    task_manager = task_server.task_manager
    concent_service = task_server.client.concent_service

    task = task_manager.tasks.get(report_computed_task.task_id, None)
    output_dir = task.tmp_dir if hasattr(task, 'tmp_dir') else None
    client_options = task_server.get_download_options(
        report_computed_task.options
    )

    fgtr = message.concents.ForceGetTaskResult(
        report_computed_task=report_computed_task
    )

    # submit a delayed `ForceGetTaskResult` to the Concent
    # in case the download exceeds the maximum allowable download time.
    # however, if it succeeds, the message will get cancelled
    # in the success handler

    concent_service.submit_task_message(
        report_computed_task.subtask_id,
        fgtr,
        msg_helpers.maximum_download_time(
            report_computed_task.size,
        ),
    )

    # Pepare callbacks for received resources
    def on_success(extracted_pkg, *_args, **_kwargs):
        logger.debug("Task result extracted %r", extracted_pkg.__dict__)

        concent_service.cancel_task_message(
            report_computed_task.subtask_id,
            'ForceGetTaskResult',
        )
        task_server.verify_results(
            report_computed_task=report_computed_task,
            extracted_package=extracted_pkg,
        )
        after_success()

    def on_error(exc, *_args, **_kwargs):
        logger.warning(
            "Task result error: %s (%s)",
            report_computed_task.subtask_id,
            exc or "unspecified",
        )

        if report_computed_task.task_to_compute.concent_enabled:
            # we're resorting to mediation through the Concent
            # to obtain the task results
            logger.debug('[CONCENT] sending ForceGetTaskResult: %s', fgtr)
            concent_service.submit_task_message(
                report_computed_task.subtask_id,
                fgtr,
            )
        after_error()

    # Actually request results
    task_manager.task_result_incoming(report_computed_task.subtask_id)
    task_manager.task_result_manager.pull_package(
        report_computed_task.multihash,
        report_computed_task.task_id,
        report_computed_task.subtask_id,
        report_computed_task.secret,
        success=on_success,
        error=on_error,
        client_options=client_options,
        output_dir=output_dir
    )

def send_report_computed_task(task_server, waiting_task_result) -> None:
    """ Send task results after finished computations
    """
    task_to_compute = history.get(
        message_class_name='TaskToCompute',
        node_id=waiting_task_result.owner.key,
        task_id=waiting_task_result.task_id,
        subtask_id=waiting_task_result.subtask_id
    )

    if not task_to_compute:
        logger.warning(
            "Cannot send ReportComputedTask. TTC missing."
            " node=%s, task_id=%r, subtask_id=%r",
            common.node_info_str(
                waiting_task_result.owner.node_name,
                waiting_task_result.owner.key,
            ),
            waiting_task_result.task_id,
            waiting_task_result.subtask_id,
        )
        return

    my_node: LocalNode = task_server.node
    client_options = task_server.get_share_options(
        waiting_task_result.task_id,
        waiting_task_result.owner.prv_addr,
    )

    report_computed_task = message.tasks.ReportComputedTask(
        task_to_compute=task_to_compute,
        node_name=my_node.node_name,
        address=my_node.prv_addr,
        port=task_server.cur_port,
        key_id=my_node.key,
        node_info=my_node.to_dict(),
        extra_data=[],
        size=waiting_task_result.result_size,
        package_hash='sha1:' + waiting_task_result.package_sha1,
        multihash=waiting_task_result.result_hash,
        secret=waiting_task_result.result_secret,
        options=client_options.__dict__,
    )

    msg_queue.put(
        waiting_task_result.owner.key,
        report_computed_task,
    )
    report_computed_task = msg_utils.copy_and_sign(
        msg=report_computed_task,
        private_key=task_server.keys_auth._private_key,  # noqa pylint: disable=protected-access
    )
    history.add(
        msg=report_computed_task,
        node_id=waiting_task_result.owner.key,
        local_role=model.Actor.Provider,
        remote_role=model.Actor.Requestor,
    )

    # if the Concent is not available in the context of this subtask
    # we can only assume that `ReportComputedTask` above reaches
    # the Requestor safely

    if not task_to_compute.concent_enabled:
        logger.debug(
            "Concent not enabled for this task, "
            "skipping `ForceReportComputedTask`. "
            "task_id=%r, "
            "subtask_id=%r, ",
            task_to_compute.task_id,
            task_to_compute.subtask_id,
        )
        return

    # we're preparing the `ForceReportComputedTask` here and
    # scheduling the dispatch of that message for later
    # (with an implicit delay in the concent service's `submit` method).
    #
    # though, should we receive the acknowledgement for
    # the `ReportComputedTask` sent above before the delay elapses,
    # the `ForceReportComputedTask` message to the Concent will be
    # cancelled and thus, never sent to the Concent.

    delayed_forcing_msg = message.concents.ForceReportComputedTask(
        report_computed_task=report_computed_task,
        result_hash='sha1:' + waiting_task_result.package_sha1
    )
    logger.debug('[CONCENT] ForceReport: %s', delayed_forcing_msg)

    task_server.client.concent_service.submit_task_message(
        waiting_task_result.subtask_id,
        delayed_forcing_msg,
    )


def send_task_failure(waiting_task_failure) -> None:
    """Inform task owner that an error occurred during task computation
    """

    task_to_compute = history.get(
        message_class_name='TaskToCompute',
        node_id=waiting_task_failure.owner.key,
        task_id=waiting_task_failure.task_id,
        subtask_id=waiting_task_failure.subtask_id
    )

    if not task_to_compute:
        logger.warning(
            "Cannot send TaskFailure. TTC missing."
            " node=%s, task_id=%r, subtask_id=%r",
            common.node_info_str(
                waiting_task_failure.owner.node_name,
                waiting_task_failure.owner.key,
            ),
            waiting_task_failure.task_id,
            waiting_task_failure.subtask_id,
        )
        return

    msg_queue.put(
        waiting_task_failure.owner.key,
        message.tasks.TaskFailure(
            task_to_compute=task_to_compute,
            err=waiting_task_failure.err_msg
        ),
    )
