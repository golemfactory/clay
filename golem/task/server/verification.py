import asyncio
import logging
import typing

from ethereum.utils import denoms

from golem_messages import message
from golem_messages import utils as msg_utils
from golem_messages.datastructures import p2p as dt_p2p
from golem_task_api.enums import VerifyResult

from apps.core.task.coretaskstate import RunVerification

from golem import model
from golem.core import common
from golem.marketplace import RequestorMarketStrategy
from golem.network import history
from golem.network.transport import msg_queue
from golem.task.taskbase import TaskResult

if typing.TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem.core import keysauth
    from golem.task import taskmanager, SubtaskId, TaskId
    from golem.task import requestedtaskmanager

logger = logging.getLogger(__name__)


class VerificationMixin:
    keys_auth: 'keysauth.KeysAuth'
    task_manager: 'taskmanager.TaskManager'
    requested_task_manager: 'requestedtaskmanager.RequestedTaskManager'

    def verify_results(
            self,
            report_computed_task: message.tasks.ReportComputedTask,
            files: typing.List[str],
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
                    node_id=node.key,
                    timeout_seconds=config_desc.disallow_node_timeout_seconds
                )
            if config_desc.disallow_ip_timeout_seconds is not None:
                # Experimental feature. Try to spread subtasks fairly amongst
                # providers.
                self.disallow_ip(
                    ip=node.pub_addr,
                    timeout_seconds=config_desc.disallow_ip_timeout_seconds,
                )

            market_strategy = self._get_market_strategy(task_id, subtask_id)
            payment_value = market_strategy.calculate_payment(
                report_computed_task
            )

            logger.info(
                "Accepting result. subtask_id=%s, "
                "provider_id=%s, payment_value=%s GNT",
                subtask_id,
                report_computed_task.provider_id,
                payment_value / denoms.ether,
            )

            payment = self.accept_result(
                task_id,
                subtask_id,
                report_computed_task.provider_id,
                task_to_compute.provider_ethereum_address,
                payment_value,
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
            failure_results = (VerifyResult.INCONCLUSIVE, VerifyResult.FAILURE)
            fut = asyncio.ensure_future(self.requested_task_manager.verify(
                task_id,
                subtask_id))
            fut.add_done_callback(
                lambda f: verification_finished(
                    False,
                    f.result() in failure_results))
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
                    files=files,
                    stats=report_computed_task.stats
                ),
                verification_finished_old,
            )

    def _get_market_strategy(
            self,
            task_id: 'TaskId',
            subtask_id: 'SubtaskId',
    ) -> typing.Type[RequestorMarketStrategy]:
        """ Retrieve the payment computing function for given
            task_id and subtask_id """
        task = self.task_manager.tasks.get(task_id)
        if task:
            return task.REQUESTOR_MARKET_STRATEGY

        task = self.requested_task_manager.get_requested_task(task_id)
        if not task:
            raise RuntimeError(
                f"Completed verification of subtask {subtask_id} "
                f"within an unknown task {task_id}")

        subtask = self.requested_task_manager.get_requested_subtask(subtask_id)
        if not subtask:
            raise RuntimeError(
                f"Completed verification of unknown subtask {subtask_id} "
                f"within task {task_id}")

        app = self.app_manager.app(task.app_id)
        if not app:
            raise RuntimeError(
                f"Completed verification of task {task_id} "
                f"created by an unknown app {task.app_id}")
        return app.market_strategy

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
