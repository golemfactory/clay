import inspect
import logging

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
def on_force_subtask_results_rejected(msg):
    # After #2349 we could reschedule ForceSubtaskResults message
    # if reason is RequestPremature (because subtask_id would be known)
    logger.warning("[CONCENT] %r", msg)


@library.register_handler(message.concents.SubtaskResultsSettled)
def on_subtask_results_settled(msg, **_):
    """End of UC3. Nothing can be done after this point.
    I'm either a Provider or Requestor
    """
    logger.warning("[CONCENT] End of Force Accept scenario by %r", msg)


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

    @handler_for(message.concents.ServiceRefused)
    def on_service_refused(self, msg,
                           response_to: message.Message = None):
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
    def on_verdict_report_computed_task(self, msg, **_):
        """Verdict is forced by Concent on Requestor

        Requestor should act as it had sent AckReportComputedTask by himself.
        """

        logger.warning("[CONCENT] Received verdict: %s", msg)

        # @todo such verification/validation should be part of `golem-messages`
        # https://github.com/golemfactory/golem-messages/issues/192

        # Verify TaskToCompute signature
        ttcs_tuple = (
            msg.ack_report_computed_task.report_computed_task.task_to_compute,
            msg.force_report_computed_task.report_computed_task.task_to_compute,
        )
        for ttc in ttcs_tuple:
            try:
                self.task_server.keys_auth.ecc.verify(
                    sig=ttc.sig,
                    inputb=ttc.get_short_hash(),
                )
            except msg_exceptions.InvalidSignature:
                logger.error(
                    '[CONCENT] Received fake TaskToCompute from Concent: %s',
                    msg,
                )
                return

        # are all ttc equal?
        if not ttcs_tuple.count(ttcs_tuple[0]) == len(ttcs_tuple):
            logger.error(
                '[CONCENT] Received differing TaskToCompute'
                ' from Concent: %s',
                msg,
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

        returned_msg = concent_helpers.process_report_computed_task(
            msg=rct,
            ecc=self.task_server.keys_auth.ecc,
            task_header_keeper=self.task_server.task_keeper,
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

        Concent sends his own ForceSubtaskResults with AckReportComputedTask
        provided by a provider.
        """
        sra = history.get('SubtaskResultsAccepted', msg.task_id, msg.subtask_id)
        srr = history.get('SubtaskResultsRejected', msg.task_id, msg.subtask_id)
        if not (sra or srr):
            #  I can't remember verification results,
            #  so try again and hope for the best
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
    def on_force_subtask_results_response(self, msg):
        """Concent forwards verified Requestors response to ForceSubtaskResults
        """
        if msg.subtask_results_accepted:
            node_id = msg.subtask_results_accepted.task_to_compute.requestor_id
            sub_msg = msg.subtask_results_accepted
            self.task_server.subtask_accepted(
                subtask_id=msg.subtask_id,
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

        wtr = self.task_server.results_to_send.get(msg.subtask_id, None)
        if not wtr:
            logger.warning(
                "Cannot find the subtask %r in the send queue", msg.subtask_id)
            return

        def success(response):
            logger.debug("Concent results upload sucessful: %r, %s",
                         msg.subtask_id, response)

        def error(exc):
            logger.warning("Concent upload failed: %r, %s",
                           msg.subtask_id, exc)

        self.concent_filetransfers.transfer(
            file_path=wtr.result_path,
            file_transfer_token=ftt,
            success=success,
            error=error)

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

        # verify if the attached `ForceGetTaskResult` bears our
        # (the requestor's) signature
        fgtr = msg.force_get_task_result

        if not fgtr or not concent_helpers.verify_message_signature(
                fgtr, self.task_server.keys_auth.ecc):
            logger.warning("ForceGetTaskResult invalid in %r", msg)
            return

        # everything okay, so we can proceed with download
        # and should download succeed,
        # we need to establish a session and proceed with the
        # normal verification procedure the same way we would do,
        # had we received the results from the Provider itself

        rct = fgtr.report_computed_task

        result_manager = self.task_server.task_manager.task_result_manager
        _, file_path = result_manager.get_file_name_and_path(
            rct.task_id, rct.subtask_id)

        task = self.task_server.task_manager.tasks.get(rct.task_id, None)
        output_dir = getattr(task, 'tmp_dir', None)

        def success(response):
            logger.debug("Concent results download sucessful: %r, %s",
                         msg.subtask_id, response)

            try:
                extracted_package = result_manager.extract(
                    file_path, output_dir, rct.secret)
            except Exception as e:  # noqa pylint:disable=broad-except
                logger.error("Concent results extraction failure: %r, %s",
                             msg.subtask_id, e)
                return

            logger.debug("Task result extracted %r",
                         extracted_package.__dict__)

            # instantiate session and run the tasksession's reaction to
            # received results
            self.task_server.verify_results(
                report_computed_task=rct,
                extracted_package=extracted_package)

        def error(exc):
            logger.warning("Concent download failed: %r, %s",
                           msg.subtask_id, exc)

        self.concent_filetransfers.transfer(
            file_path=file_path,
            file_transfer_token=ftt,
            success=success,
            error=error,
        )
