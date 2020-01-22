import inspect
import logging

from ethereum.utils import denoms
from golem_messages import exceptions as msg_exceptions
from golem_messages import message

from golem.model import Actor
from golem.network import history
from golem.network.concent import helpers as concent_helpers
from golem.network.concent.handlers_library import library
from golem.task import taskserver
from golem.task.server import helpers as task_server_helpers

from .filetransfers import ConcentFiletransferService

logger = logging.getLogger(__name__)


def handler_for(msg_cls: message.base.Message):
    def wrapped(f):
        f.handler_for = msg_cls
        return f
    return wrapped


def register_handlers(instance) -> None:
    for _, method in inspect.getmembers(instance, inspect.ismethod):
        try:
            msg_cls = method.handler_for
        except AttributeError:
            continue
        library.register_handler(msg_cls)(method)


@library.register_handler(message.concents.ForceReportComputedTaskResponse)
def on_force_report_computed_task_response(msg, **_):
    """Concents response to Provider to his ForceReportComputedTask
    """
    if msg.reject_report_computed_task:
        node_id = msg.reject_report_computed_task.task_to_compute.requestor_id
    elif msg.ack_report_computed_task:
        node_id = msg.ack_report_computed_task.\
            report_computed_task.task_to_compute.requestor_id
    else:
        logger.warning("Can't determine node_id from %r. Assuming None", msg)
        node_id = None

    history.add(
        msg=msg,
        node_id=node_id,
        local_role=Actor.Provider,
        remote_role=Actor.Concent,
    )
    reasons = message.concents.ForceReportComputedTaskResponse.REASON

    if msg.reason == reasons.SubtaskTimeout:
        # Is reject_report_computed_task created and attached by concent?
        logger.warning("[CONCENT] SubtaskTimeout for subtask: %r", msg)
        return

    if msg.reason in (reasons.ConcentAck, reasons.AckFromRequestor):
        logger.warning(
            "[CONCENT] %s for subtask: %r",
            msg.reason,
            msg.subtask_id,
        )
        if msg.reason == reasons.ConcentAck:
            remote_role = Actor.Concent
        else:
            remote_role = Actor.Requestor
        history.add(
            msg=msg.ack_report_computed_task,
            node_id=node_id,
            local_role=Actor.Provider,
            remote_role=remote_role,
        )
        return

    if msg.reason == reasons.RejectFromRequestor:
        logger.warning(
            "[CONCENT] Reject for subtask: %r",
            msg.subtask_id,
        )
        history.add(
            msg=msg.reject_report_computed_task,
            node_id=node_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )
        return

    raise RuntimeError("Illegal condition caused by {}".format(msg))


@library.register_handler(message.concents.ForceSubtaskResultsRejected)
def on_force_subtask_results_rejected(msg, **_):
    # After #2349 we could reschedule ForceSubtaskResults message
    # if reason is RequestPremature (because subtask_id would be known)
    logger.warning("[CONCENT] %r", msg)


@library.register_handler(message.concents.ForcePaymentRejected)
def on_force_payment_rejected(msg, **_):
    logger.warning("[CONCENT] ForcePaymentRejected by %r", msg)
    if msg.reason is msg.REASON.TimestampError:
        logger.warning(
            "[CONCENT] Payment rejected due to time issue."
            " Please check your clock",
        )


class TaskServerMessageHandler():
    """Container for received message handlers that require TaskServer."""
    def __init__(self, task_server: taskserver.TaskServer) -> None:
        self.task_server = task_server
        register_handlers(self)

    @property
    def concent_service(self):
        return self.task_server.client.concent_service

    @property
    def concent_filetransfers(self) -> ConcentFiletransferService:
        return self.task_server.client.concent_filetransfers

    def is_ours(self,
                parent_msg: message.base.Message,
                child_msg_field: str) -> bool:
        """
        verify if the attached message bears our signature

        :param parent_msg: the message that contains our orignal message
        :param child_msg_field: the field to check
        :return: bool: whether the field is present and correct
        """
        child_msg = getattr(parent_msg, child_msg_field, None)

        if child_msg:
            try:
                pubkey = self.task_server.keys_auth.ecc.raw_pubkey
                logger.debug("Verifying message %s against our pubkey: %s",
                             child_msg, pubkey)
                return child_msg.verify_signature(
                    public_key=pubkey)
            except msg_exceptions.InvalidSignature:
                pass

        logger.warning("Signature invalid in %r.%s",
                       child_msg_field, parent_msg)
        return False

    @handler_for(message.concents.ServiceRefused)
    def on_service_refused(self, msg,
                           response_to: message.base.Message = None):
        logger.warning(
            "Concent service (%s) refused for subtask_id: %r %s",
            response_to.__class__.__name__ if response_to else '',
            msg.subtask_id,
            msg.reason,
        )

        if isinstance(response_to, message.concents.ForceGetTaskResult):
            self.task_server.task_manager.task_computation_failure(
                msg.subtask_id,
                'Concent refused to assist in forced results download'
            )

    @handler_for(message.concents.VerdictReportComputedTask)
    def on_verdict_report_computed_task(
            self, msg: message.concents.VerdictReportComputedTask, **_):
        """Verdict is forced by Concent on Requestor

        Requestor should act as it had sent AckReportComputedTask by himself.
        """

        logger.warning("[CONCENT] Received verdict: %s", msg)

        try:
            msg.is_valid()
            concent_key = self.task_server.client.concent_variant['pubkey']
            msg.verify_owners(
                requestor_public_key=self.task_server.keys_auth.ecc.raw_pubkey,
                concent_public_key=concent_key,
            )
        except msg_exceptions.ValidationError as e:
            logger.error(
                '[CONCENT] Got corrupted TaskToCompute from Concent: %s (%s)',
                msg, e
            )
            return

        rct = msg \
            .force_report_computed_task \
            .report_computed_task

        self._after_ack_report_computed_task(
            report_computed_task=rct,
        )

    @handler_for(message.concents.ForceReportComputedTask)
    def on_force_report_computed_task(self, msg, **_):
        """Concent forwarded ReportComputedTask from Provider

        Requestor should answer to Concent with either AckReportComputedTask
        or RejectReportComputedTask
        """
        rct = msg.report_computed_task

        returned_msg = concent_helpers \
            .process_report_computed_task_no_time_check(
                msg=rct,
                ecc=self.task_server.keys_auth.ecc,
            )
        self.concent_service.submit_task_message(
            rct.subtask_id,
            returned_msg,
        )

        if isinstance(returned_msg, message.tasks.RejectReportComputedTask):
            return

        self._after_ack_report_computed_task(
            report_computed_task=rct,
        )

    @handler_for(message.concents.ForceSubtaskResults)
    def on_force_subtask_results(self, msg, **_):
        """I'm a Requestor

        Concent sends its own ForceSubtaskResults with AckReportComputedTask
        provided by a provider.
        """
        sra = history.get(
            message_class_name='SubtaskResultsAccepted',
            node_id=msg.provider_id,
            subtask_id=msg.subtask_id,
            task_id=msg.task_id
        )
        srr = history.get(
            message_class_name='SubtaskResultsRejected',
            node_id=msg.provider_id,
            subtask_id=msg.subtask_id,
            task_id=msg.task_id
        )
        if not (sra or srr):
            fgtrf = history.get(
                message_class_name='ForceGetTaskResultFailed',
                node_id=msg.provider_id,
                subtask_id=msg.subtask_id,
                task_id=msg.task_id
            )
            if fgtrf:
                srr = message.tasks.SubtaskResultsRejected(
                    report_computed_task=(
                        msg.ack_report_computed_task.report_computed_task),
                    force_get_task_result_failed=fgtrf,
                    reason=(message.tasks.SubtaskResultsRejected.REASON
                            .ForcedResourcesFailure),
                )
            else:
                #  I can't remember verification results and I have no proof of
                #  failure from Concent, so try again and hope for the best
                self._after_ack_report_computed_task(
                    report_computed_task=msg.ack_report_computed_task
                    .report_computed_task,
                )
                return

        response_msg = message.concents.ForceSubtaskResultsResponse(
            subtask_results_accepted=sra,
            subtask_results_rejected=srr,
        )
        self.concent_service.submit_task_message(
            response_msg.subtask_id,
            response_msg,
        )

    def _after_ack_report_computed_task(self, report_computed_task):
        logger.info(
            "After AckReportComputedTask. Starting verification of %r",
            report_computed_task,
        )
        task_server_helpers.computed_task_reported(
            task_server=self.task_server,
            report_computed_task=report_computed_task,
        )

    @handler_for(message.concents.ForceGetTaskResultFailed)
    def on_force_get_task_result_failed(self, msg, **_):
        """
        Concent acknowledges a failure to retrieve the task results from
        the Provider.

        The only thing we can do at this moment is to mark the task as failed
        and preserve this message for possible later usage in case the
        Provider demands payment or tries to force acceptance.
        """

        history.add(
            msg,
            node_id=msg.task_to_compute.provider_id,
            local_role=Actor.Requestor,
            remote_role=Actor.Concent,
            sync=True,
        )

        self.task_server.task_manager.task_computation_failure(
            msg.subtask_id,
            'Error downloading the task result through the Concent'
        )

    @handler_for(message.concents.ForceSubtaskResultsResponse)
    def on_force_subtask_results_response(self, msg, **_):
        """Concent forwards verified Requestors response to ForceSubtaskResults
        """
        if msg.subtask_results_accepted:
            ttc = msg.subtask_results_accepted.task_to_compute
            node_id = ttc.requestor_id
            sub_msg = msg.subtask_results_accepted
            self.task_server.subtask_accepted(
                sender_node_id=msg.requestor_id,
                task_id=msg.task_id,
                subtask_id=msg.subtask_id,
                payer_address=ttc.requestor_ethereum_address,
                value=ttc.price,
                accepted_ts=msg.subtask_results_accepted.payment_ts,
            )
        elif msg.subtask_results_rejected:
            node_id = msg.subtask_results_rejected \
                .report_computed_task \
                .task_to_compute.requestor_id
            sub_msg = msg.subtask_results_rejected
            self.task_server.subtask_rejected(
                subtask_id=msg.subtask_id,
            )
        else:
            raise RuntimeError("Illegal condition caused by {}".format(msg))

        history.add(
            msg=sub_msg,
            node_id=node_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )

    @handler_for(message.concents.ForceGetTaskResultRejected)
    def on_force_get_task_result_rejected(self, msg, **_):
        """
        Concent rejects a `ForceGetTaskResult` request, giving a reason.
        """

        logger.warning(
            "ForceGetTaskResult request has been rejected for subtask: %r %s",
            msg.subtask_id,
            msg.reason,
        )

        self.task_server.task_manager.task_computation_failure(
            msg.subtask_id,
            'Concent claims ForceGetTaskResult no longer possible'
        )

    # pylint: disable=no-self-use

    @handler_for(message.concents.AckForceGetTaskResult)
    def on_ack_force_get_task_result(self, msg, **_):
        """
        Concent accepts a `ForceGetTaskResult` request
        """
        logger.debug(
            "ForceGetTaskResult has been accepted by the Concent, subtask: %r",
            msg.subtask_id,
        )

    # pylint:enable=no-self-use

    @staticmethod
    def _log_ftt_invalid(msg: message.base.Message):
        logger.warning("File Transfer Token invalid in %r", msg)

    def _upload_results(
            self,
            subtask_id: str,
            ftt: message.concents.FileTransferToken) -> None:
        wtr = self.task_server.results_to_send.get(subtask_id, None)
        if not wtr:
            logger.warning(
                "Cannot find the subtask %r in the send queue", subtask_id)
            return

        def success(response):
            logger.debug("Concent results upload successful: %r, %s",
                         subtask_id, response)

        def error(exc):
            logger.warning("Concent results upload failed: %r, %s",
                           subtask_id, exc)

        self.concent_filetransfers.transfer(
            file_path=wtr.package_path,
            file_transfer_token=ftt,
            success=success,
            error=error,
            file_category=message.concents.FileTransferToken.
            FileInfo.Category.results
        )

    def _upload_task_resources(
            self,
            task_id: str,
            ftt: message.concents.FileTransferToken) -> None:
        package_paths = self.task_server.task_manager.comp_task_keeper\
            .get_package_paths(task_id)

        logger.debug("Package paths: %s", package_paths)

        if not package_paths:
            logger.warning("Cannot upload resources,"
                           "package not found for task: %s",
                           task_id)
            return

        def success(response):
            logger.debug("Concent resources upload successful: %r, %s",
                         task_id, response)

        def error(exc):
            logger.warning("Concent resources upload failed: %r, %s",
                           task_id, exc)

        self.concent_filetransfers.transfer(
            # for now, assuming there's always one entry
            file_path=package_paths[0],
            file_transfer_token=ftt,
            success=success,
            error=error,
            file_category=message.concents.FileTransferToken.
            FileInfo.Category.resources
        )

    @handler_for(message.concents.ForceGetTaskResultUpload)
    def on_force_get_task_result_upload(
            self, msg: message.concents.ForceGetTaskResultUpload, **_):
        """
        Concent requests an upload from a Provider
        """
        logger.debug(
            "Concent requests a results upload, subtask: %r", msg.subtask_id)

        ftt = msg.file_transfer_token
        if not ftt or not ftt.is_upload:
            self._log_ftt_invalid(msg)
            return

        self._upload_results(msg.subtask_id, ftt)

    @handler_for(message.concents.ForceGetTaskResultDownload)
    def on_force_get_task_results_download(
            self, msg: message.concents.ForceGetTaskResultDownload, **_):
        """
        Concent informs the Requestor that the results are available for
        download from the Concent.
        """
        logger.debug(
            "Results available for download from the Concent, subtask: %r",
            msg.subtask_id)

        ftt = msg.file_transfer_token
        if not ftt or not ftt.is_download:
            self._log_ftt_invalid(msg)
            return

        # ugh... for some reason, the Concent rewrites the FGTR
        # instead of passing it along...
        #
        # # verify if the attached `ForceGetTaskResult` bears our
        # # (the requestor's) signature
        # if not self.is_ours(msg, 'force_get_task_result'):
        #     return

        # everything okay, so we can proceed with download
        # and should download succeed,
        # we need to establish a session and proceed with the
        # normal verification procedure the same way we would do,
        # had we received the results from the Provider itself

        rct = msg.force_get_task_result.report_computed_task

        result_manager = self.task_server.task_manager.task_result_manager
        _, file_path = result_manager.get_file_name_and_path(
            rct.task_id, rct.subtask_id)

        task = self.task_server.task_manager.tasks.get(rct.task_id, None)
        output_dir = getattr(task, 'tmp_dir', None)
        is_task_api_task = self.task_server.requested_task_manager.task_exists(
            rct.task_id)

        def success(response):
            logger.debug("Concent results download successful: %r, %s",
                         msg.subtask_id, response)

            try:
                extracted_package = result_manager.extract_zip(
                    file_path, output_dir)
            except Exception as e:  # noqa pylint:disable=broad-except
                logger.error("Concent results extraction failure: %r, %s",
                             msg.subtask_id, e)
                return

            files = [str(extracted_package)] \
                if is_task_api_task \
                else extracted_package.get_full_path_files()

            logger.debug("Task result downloaded: %r", files)

            # instantiate session and run the tasksession's reaction to
            # received results
            self.task_server.verify_results(
                report_computed_task=rct,
                files=files)

        def error(exc):
            logger.warning("Concent download failed: %r, %s",
                           msg.subtask_id, exc)

        self.concent_filetransfers.transfer(
            file_path=file_path,
            file_transfer_token=ftt,
            success=success,
            error=error,
        )

    @handler_for(message.concents.AckSubtaskResultsVerify)
    def on_ack_subtask_results_verify(
            self, msg: message.concents.AckSubtaskResultsVerify, **_):
        """
        Concent acknowledges the reception of the `SubtaskResultsVerify`
        message and grants upload access using the attached `FileTransferToken`
        """

        logger.debug(
            "Results available for download from the Concent, subtask: %r",
            msg.subtask_id)

        ftt = msg.file_transfer_token
        if not ftt or not ftt.is_upload:
            self._log_ftt_invalid(msg)
            return

        if not self.is_ours(msg, 'subtask_results_verify'):
            return

        self._upload_task_resources(msg.task_id, ftt)
        self._upload_results(msg.subtask_id, ftt)

    @handler_for(message.concents.SubtaskResultsSettled)
    def on_subtask_results_settled(self, msg, **_):
        """
        Sent from the Concent to either the Provider or to the Requestor.
        It effectively ends processing for UC3/UC4 scenarios.
        The task has been paid for from the Deposit by the Concent.
        """
        logger.info("[CONCENT] End of Force Accept/Verify scenario by %r", msg)

        # if the receiving party is the Provider,
        # mark the income as coming from the Concent

        if msg.provider_id == self.task_server.client.node.key:
            self.task_server.subtask_settled(
                sender_node_id=msg.requestor_id,
                subtask_id=msg.subtask_id,
                settled_ts=msg.timestamp,
            )

    @handler_for(message.concents.ForcePaymentCommitted)
    def on_force_payment_committed(self, msg, **_):
        if msg.recipient_type == msg.Actor.Requestor:
            handler = self.on_force_payment_committed_for_requestor
        elif msg.recipient_type == msg.Actor.Provider:
            handler = self.on_force_payment_committed_for_provider
        else:
            raise ValueError(
                "Unknown Actor: {!r}".format(msg.recipient_type),
            )
        handler(msg)

    def on_force_payment_committed_for_requestor(self, msg):  # noqa pylint: disable=no-self-use
        logger.warning(
            "[CONCENT] Our deposit was used to cover payment of %.6f GNT"
            " for eth address: %s",
            msg.amount_paid / denoms.ether,
            msg.provider_eth_account,
        )
        # Stopping of awaiting payment will be handled
        # when blockchain event is detected

    def on_force_payment_committed_for_provider(self, msg):  # noqa pylint: disable=no-self-use
        # This informative/redundant.
        # SEE: golem.transactions.ethereum.ethereumincomeskeeper
        #      ._on_forced_payment
        logger.debug(
            "[CONCENT] Forced payment from % should be on blockchain."
            " Will wait for that.",
            msg.task_owner_key,
        )
