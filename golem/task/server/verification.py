import asyncio
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
from golem.task.taskbase import TaskResult
from golem.task.result.resultmanager import ExtractedPackage

if typing.TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem.core import keysauth
    from golem.task import taskmanager
    from golem.task import requestedtaskmanager

logger = logging.getLogger(__name__)


class VerificationMixin:
    keys_auth: 'keysauth.KeysAuth'
    task_manager: 'taskmanager.TaskManager'
    requested_task_manager: 'requestedtaskmanager.RequestedTaskManager'

    def verify_results(
            self,
            report_computed_task: message.tasks.ReportComputedTask,
            extracted_package: ExtractedPackage,
    ) -> None:
        node = dt_p2p.Node(**report_computed_task.node_info)
        task_id = report_computed_task.task_id
        subtask_id = report_computed_task.subtask_id
        logger.info(
            'Verifying results. node=%s, subtask_id=%s',
            common.node_info_str(
                node.node_name,
                node.key,
            ),
            subtask_id,
        )

        def verification_finished(
                is_verification_lenient: bool,
                verification_failed: bool,
        ):
            logger.debug("Verification finished handler.")

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

            if task_id in self.task_manager.tasks:
                task = self.task_manager.tasks[task_id]
                strategy = task.REQUESTOR_MARKET_STRATEGY
                payment_computer = strategy.get_payment_computer(  # noqa type: ignore
                        task,
                        subtask_id)
            else:
                # FIXME: adjust after merging #4753 (with #4785)
                task = self.requested_task_manager.get_requested_task(task_id)
                subtask_timeout = task.subtask_timeout

                def payment_computer(price: int):
                    return price * subtask_timeout

            payment = self.accept_result(
                task_id,
                subtask_id,
                report_computed_task.provider_id,
                task_to_compute.provider_ethereum_address,
                payment_computer(task_to_compute.want_to_compute_task.price),
                unlock_funds=not (verification_failed
                                  and is_verification_lenient),
            )

            response_msg = message.tasks.SubtaskResultsAccepted(
                report_computed_task=report_computed_task,
                payment_ts=int(payment.created_date.timestamp()),
            )

            signed_response_msg = msg_utils.copy_and_sign(
                msg=response_msg,
                private_key=self.keys_auth._private_key,  # noqa pylint: disable=protected-access
            )

            msg_queue.put(node.key, response_msg)

            history.add(
                signed_response_msg,
                node_id=task_to_compute.provider_id,
                local_role=model.Actor.Requestor,
                remote_role=model.Actor.Provider,
            )

        if self.requested_task_manager.task_exists(task_id):
            task = asyncio.ensure_future(self.requested_task_manager.verify(
                task_id,
                subtask_id,
            ))
            task.add_done_callback(
                lambda r: verification_finished(False, r.is_failure()))
        else:
            def verification_finished_old():
                is_verification_lenient = (
                    self.task_manager.tasks[task_id].task_definition
                    .run_verification == RunVerification.lenient)
                verification_failed = \
                    not self.task_manager.verify_subtask(subtask_id)
                verification_finished(
                    is_verification_lenient,
                    verification_failed,
                )

            self.task_manager.computed_task_received(
                subtask_id,
                TaskResult(
                    files=extracted_package.get_full_path_files(),
                    stats=report_computed_task.stats
                ),
                verification_finished_old,
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

        signed_response_msg = msg_utils.copy_and_sign(
            msg=response_msg,
            private_key=self.keys_auth._private_key,  # noqa pylint: disable=protected-access
        )

        msg_queue.put(node.key, response_msg)

        history.add(
            signed_response_msg,
            node_id=report_computed_task.task_to_compute.provider_id,
            local_role=model.Actor.Requestor,
            remote_role=model.Actor.Provider,
        )
