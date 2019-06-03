import logging
import typing

from golem_messages import message
from golem_messages import utils as msg_utils
from golem_messages.datastructures import p2p as dt_p2p

from apps.core.task.coretaskstate import RunVerification

from golem import model
from golem.core import common
from golem.network import history
from golem.network.transport import msg_queue
from golem.task.result.resultmanager import ExtractedPackage

if typing.TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem.core import keysauth
    from golem.task import taskmanager

logger = logging.getLogger(__name__)


class VerificationMixin:
    keys_auth: 'keysauth.KeysAuth'
    task_manager: 'taskmanager.TaskManager'

    def verify_results(
            self,
            report_computed_task: message.tasks.ReportComputedTask,
            extracted_package: ExtractedPackage,
    ) -> None:

        node = dt_p2p.Node(**report_computed_task.node_info)
        subtask_id = report_computed_task.subtask_id
        logger.info(
            'Verifying results. node=%s, subtask_id=%s',
            common.node_info_str(
                node.node_name,
                node.key,
            ),
            subtask_id,
        )
        result_files = extracted_package.get_full_path_files()

        def verification_finished():
            logger.debug("Verification finished handler.")

            task_id = self.task_manager.subtask_to_task(
                subtask_id, model.Actor.Requestor)
            is_verification_lenient = (
                self.task_manager.tasks[task_id]
                .task_definition.run_verification == RunVerification.lenient)

            verification_failed = \
                not self.task_manager.verify_subtask(subtask_id)
            if verification_failed:
                if not is_verification_lenient:
                    logger.debug("Verification failure. subtask_id=%r",
                                 subtask_id)
                    self.send_result_rejected(
                        report_computed_task=report_computed_task,
                        reason=message.tasks.SubtaskResultsRejected.REASON
                        .VerificationNegative
                    )
                    return
                logger.info("Verification failed, but I'm paying anyway."
                            " subtask_id=%s", subtask_id)

            task_to_compute = report_computed_task.task_to_compute

            config_desc = self.config_desc
            if config_desc.disallow_node_timeout_seconds is not None:
                # Experimental feature. Try to spread subtasks fairly amongst
                # providers.
                self.disallow_node(
                    node_id=task_to_compute.provider_id,
                    timeout_seconds=config_desc.disallow_node_timeout_seconds,
                    persist=False,
                )
            if config_desc.disallow_ip_timeout_seconds is not None:
                # Experimental feature. Try to spread subtasks fairly amongst
                # providers.
                self.disallow_ip(
                    ip=self.address,
                    timeout_seconds=config_desc.disallow_ip_timeout_seconds,
                )

            payment_processed_ts = self.accept_result(
                subtask_id,
                report_computed_task.provider_id,
                task_to_compute.provider_ethereum_address,
                task_to_compute.price,
                unlock_funds=not (verification_failed
                                  and is_verification_lenient),
            )

            response_msg = message.tasks.SubtaskResultsAccepted(
                report_computed_task=report_computed_task,
                payment_ts=payment_processed_ts,
            )
            msg_queue.put(node.key, response_msg)
            history.add(
                msg_utils.copy_and_sign(
                    msg=response_msg,
                    private_key=self.keys_auth._private_key,  # noqa pylint: disable=protected-access
                ),
                node_id=task_to_compute.provider_id,
                local_role=model.Actor.Requestor,
                remote_role=model.Actor.Provider,
            )

        self.task_manager.computed_task_received(
            subtask_id,
            result_files,
            verification_finished
        )

    def send_result_rejected(
            self,
            report_computed_task: message.tasks.ReportComputedTask,
            reason: message.tasks.SubtaskResultsRejected.REASON,
    ) -> None:
        """
        Inform that result doesn't pass the verification or that
        the verification was not possible

        :param str subtask_id: subtask that has wrong result
        :param SubtaskResultsRejected.Reason reason: the rejection reason
        """


        logger.debug(
            'send_result_rejected. reason=%r, rct=%r',
            reason,
            report_computed_task,
        )

        node = dt_p2p.Node(**report_computed_task.node_info)

        self.reject_result(  # type: ignore
            report_computed_task.subtask_id,
            node.key,
        )

        response_msg = message.tasks.SubtaskResultsRejected(
            report_computed_task=report_computed_task,
            reason=reason,
        )
        msg_queue.put(node.key, response_msg)

        response_msg = msg_utils.copy_and_sign(
            msg=response_msg,
            private_key=self.keys_auth._private_key,  # noqa pylint: disable=protected-access
        )
        history.add(
            response_msg,
            node_id=report_computed_task.task_to_compute.provider_id,
            local_role=model.Actor.Requestor,
            remote_role=model.Actor.Provider,
        )
