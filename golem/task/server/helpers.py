import logging

from golem_messages import message
from golem_messages import helpers as msg_helpers

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
        report_computed_task.options,
        report_computed_task.task_id,
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
