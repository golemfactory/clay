# pylint: disable=protected-access,no-self-use,no-member
import datetime
import gc
import importlib
import unittest
import unittest.mock as mock

import factory
from golem_messages import cryptography
from golem_messages import exceptions as msg_exceptions
from golem_messages import factories as msg_factories
from golem_messages import message
from golem_messages import utils as msg_utils
from golem_messages.factories.datastructures.tasks import TaskHeaderFactory
from golem_messages.message.concents import FileTransferToken

from golem import testutils
from golem.core import keysauth
from golem.core import variables
from golem.model import Actor
from golem.network import history
from golem.network.concent import received_handler
from golem.network.concent.handlers_library import library
from golem.network.concent.filetransfers import ConcentFiletransferService


from tests.factories import taskserver as taskserver_factories
from tests.factories.resultpackage import ExtractedPackageFactory


class RegisterHandlersTestCase(unittest.TestCase):
    def setUp(self):
        library._handlers = {}

    def test_register_handlers(self):
        class MyHandler:
            def not_a_handler(self, msg):
                pass

            @received_handler.handler_for(message.p2p.Ping)
            def ping_handler(self, msg):
                pass

        instance = MyHandler()
        received_handler.register_handlers(instance)
        self.assertEqual(len(library._handlers), 1)
        self.assertEqual(
            library._handlers[message.p2p.Ping](),
            instance.ping_handler,
        )


class FrctResponseTestBase(unittest.TestCase):

    def _get_frctr(self):
        raise NotImplementedError()

    def setUp(self):
        # Avoid warnings caused by previous tests leaving handlers
        library._handlers = {}

        self.msg = self._get_frctr()
        self.reasons = message.concents.ForceReportComputedTaskResponse.REASON
        ttc = self.msg.task_to_compute
        self.call_response = mock.call(
            msg=self.msg,
            node_id=ttc.requestor_id if ttc else None,
            local_role=Actor.Provider,
            remote_role=Actor.Concent,
        )
        importlib.reload(received_handler)

    def tearDown(self):
        library._handlers = {}


@mock.patch("golem.network.history.add")
class TestOnForceReportComputedTaskResponsePlain(FrctResponseTestBase):
    def _get_frctr(self):
        return msg_factories.concents.\
            ForceReportComputedTaskResponseFactory()

    def test_subtask_timeout(self, add_mock):
        self.msg.ack_report_computed_task = None
        self.msg.reject_report_computed_task = None
        self.msg.reason = self.reasons.SubtaskTimeout
        library.interpret(self.msg)
        add_mock.assert_called_once_with(
            msg=self.msg,
            node_id=None,
            local_role=Actor.Provider,
            remote_role=Actor.Concent,
        )


@mock.patch("golem.network.history.add")
class TestOnForceReportComputedTaskResponseAck(FrctResponseTestBase):
    def _get_frctr(self):
        return msg_factories.concents.\
            ForceReportComputedTaskResponseFactory.\
            with_ack_report_computed_task()

    def test_concent_ack(self, add_mock):
        self.msg.reason = self.reasons.ConcentAck
        library.interpret(self.msg)
        ttc = self.msg.task_to_compute
        call_inner = mock.call(
            msg=self.msg.ack_report_computed_task,
            node_id=ttc.requestor_id,
            local_role=Actor.Provider,
            remote_role=Actor.Concent,
        )
        self.assertEqual(add_mock.call_count, 2)
        add_mock.assert_has_calls([
            self.call_response,
            call_inner,
        ])

    def test_ack_from_requestor(self, add_mock):
        self.msg.reason = self.reasons.AckFromRequestor
        library.interpret(self.msg)
        ttc = self.msg.task_to_compute
        self.assertEqual(add_mock.call_count, 2)
        call_inner = mock.call(
            msg=self.msg.ack_report_computed_task,
            node_id=ttc.requestor_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )
        add_mock.assert_has_calls([
            self.call_response,
            call_inner,
        ])


@mock.patch("golem.network.history.add")
class TestOnForceReportComputedTaskResponseReject(FrctResponseTestBase):
    def _get_frctr(self):
        return msg_factories.concents. \
            ForceReportComputedTaskResponseFactory. \
            with_reject_report_computed_task()

    def test_reject_from_requestor(self, add_mock):
        self.msg.reason = self.reasons.RejectFromRequestor
        library.interpret(self.msg)
        ttc = self.msg.task_to_compute
        self.assertEqual(add_mock.call_count, 2)
        call_inner = mock.call(
            msg=self.msg.reject_report_computed_task,
            node_id=ttc.requestor_id,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )
        add_mock.assert_has_calls([
            self.call_response,
            call_inner,
        ])


class TaskServerMessageHandlerTestBase(
        testutils.DatabaseFixture, testutils.TestWithClient):

    @mock.patch('golem.envs.docker.cpu.deferToThread',
                lambda f, *args, **kwargs: f(*args, **kwargs))
    def setUp(self):
        # Avoid warnings caused by previous tests leaving handlers
        library._handlers = {}

        super().setUp()
        self.task_server = taskserver_factories.TaskServer(
            client=self.client,
        )
        history.MessageHistoryService()
        # received_handler.TaskServerMessageHandler is instantiated
        # in TaskServer.__init__

        self.cf_transfer = self.client.concent_filetransfers.transfer

        self.provider_keys = cryptography.ECCx(None)
        self.concent_keys = cryptography.ECCx(None)
        self.requestor_keys = cryptography.ECCx(None)
        self.client.concent_variant = {
            'pubkey': self.concent_keys.raw_pubkey
        }

    def tearDown(self):
        # Remove registered handlers
        del self.task_server
        gc.collect()
        super().tearDown()


class IsOursTest(TaskServerMessageHandlerTestBase):
    def setUp(self):
        super().setUp()
        self.task_server.keys_auth.ecc.raw_pubkey = \
            self.provider_keys.raw_pubkey
        with mock.patch('golem.network.concent.'
                        'received_handler.register_handlers'):
            self.tsmh = received_handler.TaskServerMessageHandler(
                task_server=self.task_server,
            )

    def test_is_ours(self):
        provider_priv_key = self.provider_keys.raw_privkey
        msg = msg_factories.concents.AckSubtaskResultsVerifyFactory(
            subtask_results_verify__sign__privkey=provider_priv_key
        )
        self.assertTrue(self.tsmh.is_ours(msg, 'subtask_results_verify'))

    def test_not_is_ours_empty_child_msg(self):
        msg = msg_factories.concents.AckSubtaskResultsVerifyFactory(
            subtask_results_verify=None
        )
        self.assertFalse(self.tsmh.is_ours(msg, 'subtask_results_verify'))

    def test_not_is_ours_sig_mismatch(self):
        other_priv_key = self.concent_keys.raw_privkey
        msg = msg_factories.concents.AckSubtaskResultsVerifyFactory(
            subtask_results_verify__sign__privkey=other_priv_key
        )
        self.assertFalse(self.tsmh.is_ours(msg, 'subtask_results_verify'))


class ServiceRefusedTest(TaskServerMessageHandlerTestBase):
    @mock.patch("golem.network.concent.received_handler.logger.warning")
    def test_concent_service_refused(self, logger_mock):
        msg = msg_factories.concents.ServiceRefusedFactory()
        library.interpret(msg)
        self.assertIn('Concent service (%s) refused',
                      logger_mock.call_args[0][0])


class VerdictReportComputedTaskFactory(TaskServerMessageHandlerTestBase):
    def setUp(self):
        super().setUp()
        self.task_server.keys_auth.ecc.raw_pubkey = \
            self.requestor_keys.raw_pubkey

    def get_vrct(self):
        wtct = msg_factories.tasks.WantToComputeTaskFactory(
            provider_public_key=msg_utils.encode_hex(
                self.provider_keys.raw_pubkey
            ),
            sign__privkey=self.provider_keys.raw_privkey,
            task_header=TaskHeaderFactory(
                sign__privkey=self.requestor_keys.raw_privkey
            )
        )
        ttc = msg_factories.tasks.TaskToComputeFactory(
            requestor_public_key=msg_utils.encode_hex(
                self.requestor_keys.raw_pubkey,
            ),
            sign__privkey=self.requestor_keys.raw_privkey,
            want_to_compute_task=wtct,
        )
        frct = msg_factories.concents.ForceReportComputedTaskFactory(
            report_computed_task__task_to_compute=ttc,
            report_computed_task__sign__privkey=self.provider_keys.raw_privkey,
            sign__privkey=self.provider_keys.raw_privkey,
        )
        msg = msg_factories.concents.VerdictReportComputedTaskFactory(
            force_report_computed_task=frct,
        )
        msg.ack_report_computed_task.sign_message(
            self.concent_keys.raw_privkey)
        msg.sign_message(self.concent_keys.raw_privkey)
        return msg

    @mock.patch(
        "golem_messages.helpers.maximum_download_time",
        return_value=datetime.timedelta(seconds=10),
    )
    @mock.patch(
        "golem.task.result.resultmanager.EncryptedResultPackageManager"
        ".pull_package")
    def test_verdict_report_computed_task(
            self,
            pull_mock,
            _mdt_mock):
        msg = self.get_vrct()
        library.interpret(msg)
        pull_mock.assert_called()

    @mock.patch("golem.task.taskserver.TaskServer.verify_results")
    @mock.patch(
        "golem_messages.helpers.maximum_download_time",
        return_value=datetime.timedelta(seconds=10),
    )
    def test_verdict_report_computed_task_invalid_sig(
            self,
            _mdt_mock,
            verify_mock):
        msg = msg_factories.concents.VerdictReportComputedTaskFactory()
        with self.assertRaises(msg_exceptions.OwnershipMismatch):
            library.interpret(msg)
        verify_mock.assert_not_called()

    @mock.patch("golem.task.taskserver.TaskServer.verify_results")
    def test_verdict_report_computed_task_diff_ttc(
            self,
            verify_mock):
        msg = msg_factories.concents.VerdictReportComputedTaskFactory()
        msg.ack_report_computed_task.report_computed_task.task_to_compute = \
            msg_factories.tasks.TaskToComputeFactory()
        self.assertNotEqual(
            msg.ack_report_computed_task.task_to_compute,
            msg.force_report_computed_task.
            report_computed_task.task_to_compute,
        )
        library.interpret(msg)
        verify_mock.assert_not_called()


class ForceReportComputedTaskTest(TaskServerMessageHandlerTestBase):

    @mock.patch(
        "golem.network.concent.helpers"
        ".process_report_computed_task_no_time_check"
    )
    @mock.patch(
        "golem_messages.helpers.maximum_download_time",
        return_value=datetime.timedelta(seconds=10),
    )
    @mock.patch(
        "golem.task.result.resultmanager.EncryptedResultPackageManager"
        ".pull_package")
    def test_force_report_computed_task(
            self,
            pull_mock,
            _mdt_mock,
            helper_mock):
        msg = msg_factories.concents.ForceReportComputedTaskFactory()
        helper_mock.return_value = returned_msg = object()
        library.interpret(msg)
        helper_mock.assert_called_once_with(
            msg=msg.report_computed_task,
            ecc=mock.ANY,
        )
        self.task_server.client.concent_service.submit_task_message \
            .assert_any_call(
                msg.report_computed_task.subtask_id,
                returned_msg)
        pull_mock.assert_called()


class ForceGetTaskResultTest(TaskServerMessageHandlerTestBase):

    @mock.patch('golem.task.taskmanager.TaskManager.task_computation_failure')
    def test_force_get_task_result_failed(self, tcf):
        fgtrf = msg_factories.concents.ForceGetTaskResultFailedFactory()
        fgtrf._fake_sign()
        library.interpret(fgtrf)

        msg = history.MessageHistoryService.get_sync_as_message(
            task=fgtrf.task_id,
            subtask=fgtrf.subtask_id,
            node=fgtrf.task_to_compute.provider_id,
            msg_cls='ForceGetTaskResultFailed',
        )

        self.assertIsInstance(msg, message.concents.ForceGetTaskResultFailed)
        tcf.assert_called_once_with(
            fgtrf.subtask_id,
            'Error downloading the task result through the Concent')

    @mock.patch('golem.task.taskmanager.TaskManager.task_computation_failure')
    def test_fgtr_service_refused(self, tcf):
        fgtr = msg_factories.concents.ForceGetTaskResultFactory()
        sr = msg_factories.concents.ServiceRefusedFactory(
            task_to_compute__subtask_id=fgtr.subtask_id)
        library.interpret(sr, response_to=fgtr)
        tcf.assert_called_once_with(
            fgtr.subtask_id,
            'Concent refused to assist in forced results download')

    @mock.patch('golem.task.taskmanager.TaskManager.task_computation_failure')
    def test_force_get_task_result_rejected(self, tcf):
        fgtrr = msg_factories.concents.ForceGetTaskResultRejectedFactory()
        library.interpret(fgtrr, response_to=fgtrr.force_get_task_result)
        tcf.assert_called_once_with(
            fgtrr.subtask_id,
            'Concent claims ForceGetTaskResult no longer possible'
        )

    @mock.patch('golem.network.concent.received_handler.logger.debug')
    def test_ack_force_get_task_result(self, log):
        afgtr = msg_factories.concents.AckForceGetTaskResultFactory()
        library.interpret(afgtr, response_to=afgtr.force_get_task_result)
        self.assertEqual(log.call_count, 1)


class ForceSubtaskResultsResponseTest(TaskServerMessageHandlerTestBase):
    def setUp(self):
        super().setUp()
        self.client.transaction_system = mock.Mock()

    def test_force_subtask_results_response_empty(self):
        msg = message.concents.ForceSubtaskResultsResponse()
        # pylint: disable=no-member
        self.assertIsNone(msg.subtask_results_accepted)
        self.assertIsNone(msg.subtask_results_rejected)
        # pylint: enable=no-member
        with self.assertRaises(RuntimeError):
            library.interpret(msg)

    @mock.patch("golem.network.history.add")
    def test_force_subtask_results_response_accepted(
            self,
            add_mock):
        msg = msg_factories.concents.\
            ForceSubtaskResultsResponseFactory.with_accepted()

        library.interpret(msg)
        self.client.transaction_system.expect_income.assert_called_once_with(
            sender_node=msg.task_to_compute.requestor_id,
            task_id=msg.task_id,
            subtask_id=msg.subtask_id,
            payer_address=msg.task_to_compute.requestor_ethereum_address,
            value=msg.task_to_compute.price,
            accepted_ts=msg.subtask_results_accepted.payment_ts,
        )

        add_mock.assert_called_once_with(
            msg=msg.subtask_results_accepted,
            node_id=mock.ANY,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )

    @mock.patch("golem.network.history.add")
    @mock.patch("golem.task.taskserver.TaskServer.subtask_rejected")
    def test_force_subtask_results_response_rejected(
            self,
            rejected_mock,
            add_mock):
        msg = msg_factories.concents.\
            ForceSubtaskResultsResponseFactory.with_rejected()
        library.interpret(msg)
        rejected_mock.assert_called_once_with(
            subtask_id=msg.subtask_id,
        )
        add_mock.assert_called_once_with(
            msg=msg.subtask_results_rejected,
            node_id=mock.ANY,
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )


class FiletransfersTestBase(TaskServerMessageHandlerTestBase):

    def setUp(self):
        super().setUp()
        self.client.concent_filetransfers = ConcentFiletransferService(
            keys_auth=keysauth.KeysAuth(
                datadir=self.path,
                private_key_name='priv_key',
                password='password',
            ),
            variant=variables.CONCENT_CHOICES['dev'],
        )

        self.cft = self.client.concent_filetransfers

        cft_patch = mock.patch(
            'golem.network.concent.filetransfers'
            '.ConcentFiletransferService.running',
            mock.Mock(return_value=True)
        )
        cft_patch.start()
        self.addCleanup(cft_patch.stop)


class FileTransferTokenTestsBase:

    def setUp(self):
        super().setUp()  # noqa: pylint:disable=no-member

        self.wtr = taskserver_factories.WaitingTaskResultFactory(
            package_path=self.path)
        self.rct = msg_factories.tasks.ReportComputedTaskFactory(
            task_to_compute__subtask_id=self.wtr.subtask_id,
            task_to_compute__task_id=self.wtr.task_id,
        )


class FileTransferTokenTests(FileTransferTokenTestsBase):
    MSG_FACTORY: factory.Factory

    def _get_correct_message(self):
        return self.MSG_FACTORY(
            force_get_task_result__report_computed_task=self.rct)

    def _get_message_without_ftt(self):
        return self.MSG_FACTORY(file_transfer_token=None)

    def _get_message_ftt_wrong_type(self):
        raise NotImplementedError()

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_no_ftt(self, log_mock):
        msg = self._get_message_without_ftt()
        library.interpret(msg)
        self.cf_transfer.assert_not_called()
        log_mock.assert_called_once()
        self.assertIn('File Transfer Token invalid', log_mock.call_args[0][0])

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_ftt_wrong_type(self, log_mock):
        msg = self._get_message_ftt_wrong_type()
        library.interpret(msg)
        self.cf_transfer.assert_not_called()
        log_mock.assert_called_once()
        self.assertIn('File Transfer Token invalid', log_mock.call_args[0][0])


class ForceGetTaskResultUploadTest(FileTransferTokenTests,  # noqa pylint:disable=too-many-ancestors
                                   FiletransfersTestBase):
    MSG_FACTORY = msg_factories.concents.ForceGetTaskResultUploadFactory

    def _get_message_ftt_wrong_type(self):
        return self.MSG_FACTORY(file_transfer_token__download=True,
                                file_transfer_token__upload=False)

    @mock.patch('golem.network.concent.received_handler.logger.debug')
    def test_force_get_task_result_upload(self, log_mock):
        fgtru = self._get_correct_message()
        self.task_server.results_to_send[self.wtr.subtask_id] = self.wtr

        library.interpret(fgtru)

        response = mock.Mock(ok=True)

        with mock.patch(
            'golem.network.concent.filetransfers'
            '.ConcentFiletransferService.upload',
            mock.Mock(return_value=response)
        ) as upload_mock:
            self.cft._run()

        upload_mock.assert_called_once()
        self.assertEqual(
            upload_mock.call_args[0][0].file_path,
            self.wtr.package_path)
        self.assertEqual(
            upload_mock.call_args[0][0].file_transfer_token,
            fgtru.file_transfer_token)

        log_mock.assert_called_with(
            "Concent results upload successful: %r, %s",
            fgtru.subtask_id,
            response)

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_force_get_task_result_upload_failed(self, log_mock):
        fgtru = self._get_correct_message()
        self.task_server.results_to_send[self.wtr.subtask_id] = self.wtr

        library.interpret(fgtru)

        exception = Exception()

        with mock.patch(
            'golem.network.concent.filetransfers'
            '.ConcentFiletransferService.upload',
            mock.Mock(side_effect=exception)
        ):
            self.cft._run()

        log_mock.assert_called_with(
            "Concent results upload failed: %r, %s",
            fgtru.subtask_id,
            exception)

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_force_get_task_result_upload_wtr_not_found(self, log_mock):
        fgtru = self._get_correct_message()
        library.interpret(fgtru)
        self.cf_transfer.assert_not_called()
        log_mock.assert_called_once()
        self.assertIn('Cannot find the subtask', log_mock.call_args[0][0])


class ForceGetTaskResultDownloadTest(FileTransferTokenTests,  # noqa pylint:disable=too-many-ancestors
                                     FiletransfersTestBase):
    MSG_FACTORY = msg_factories.concents.ForceGetTaskResultDownloadFactory

    def setUp(self):
        super().setUp()
        self.task_server.keys_auth.ecc.raw_pubkey = \
            self.requestor_keys.raw_pubkey

    def _get_message_ftt_wrong_type(self):
        return self.MSG_FACTORY(file_transfer_token__download=False,
                                file_transfer_token__upload=True)

    def _get_correct_message(self):
        msg = super()._get_correct_message()
        msg.force_get_task_result.sign_message(
            private_key=self.requestor_keys.raw_privkey)
        self.assertTrue(
            msg.force_get_task_result.verify_signature(
                self.requestor_keys.raw_pubkey))
        return msg

    def test_force_get_task_result_download(self):
        fgtrd = self._get_correct_message()

        library.interpret(fgtrd)

        ep = ExtractedPackageFactory()

        extract = \
            self.task_server.task_manager.task_result_manager.extract_zip = \
            mock.Mock(return_value=ep)

        verify_results = self.task_server.verify_results = mock.Mock()

        with mock.patch(
            'golem.network.concent.filetransfers'
            '.ConcentFiletransferService.download',
        ) as download_mock:
            self.cft._run()

        download_mock.assert_called_once()
        self.assertEqual(
            download_mock.call_args[0][0].file_transfer_token,
            fgtrd.file_transfer_token)

        extract.assert_called_once()
        verify_results.assert_called_once_with(
            report_computed_task=self.rct, files=ep.get_full_path_files()
        )

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_force_get_task_result_download_failed(self, log_mock):
        fgtrd = self._get_correct_message()

        library.interpret(fgtrd)

        exception = Exception()

        with mock.patch(
            'golem.network.concent.filetransfers'
            '.ConcentFiletransferService.download',
            mock.Mock(side_effect=exception)
        ):
            self.cft._run()

        log_mock.assert_called_with(
            "Concent download failed: %r, %s",
            self.rct.subtask_id, exception
        )

    @mock.patch('golem.network.concent.received_handler.logger.error')
    def test_force_get_task_result_download_extraction_failed(self, log_mock):
        fgtrd = self._get_correct_message()

        library.interpret(fgtrd)

        exception = Exception()
        extract = \
            self.task_server.task_manager.task_result_manager.extract_zip = \
            mock.Mock(side_effect=exception)

        with mock.patch(
            'golem.network.concent.filetransfers'
            '.ConcentFiletransferService.download',
        ):
            self.cft._run()

        extract.assert_called_once()
        log_mock.assert_called_with(
            "Concent results extraction failure: %r, %s",
            fgtrd.subtask_id, exception
        )


class ForceSubtaskResultsTest(TaskServerMessageHandlerTestBase):
    def setUp(self):
        super().setUp()
        self.msg = msg_factories.concents.ForceSubtaskResultsFactory()

    @mock.patch('golem.network.history.get')
    @mock.patch(
        'golem.network.concent.received_handler'
        '.TaskServerMessageHandler.'
        '_after_ack_report_computed_task')
    def test_no_sra_nor_srr(self, last_resort_mock, get_mock):
        get_mock.return_value = None
        library.interpret(self.msg)
        last_resort_mock.assert_called_once_with(
            report_computed_task=self.msg
            .ack_report_computed_task
            .report_computed_task,
        )

    @mock.patch('golem.network.history.get')
    @mock.patch(
        'golem.network.concent.received_handler'
        '.TaskServerMessageHandler.'
        '_after_ack_report_computed_task')
    def test_no_sra_nor_srr_but_has_fgtrf(self, last_resort_mock, get_mock):
        fgtrf = msg_factories.concents.ForceGetTaskResultFailedFactory(
            task_to_compute__subtask_id=self.msg.subtask_id,
        )

        def history_get(*, message_class_name, **_kwargs):
            if message_class_name == 'ForceGetTaskResultFailed':
                return fgtrf
            return None

        get_mock.side_effect = history_get

        library.interpret(self.msg)

        last_resort_mock.assert_not_called()
        self.task_server.client.concent_service.submit_task_message \
            .assert_called_once_with(
                self.msg.subtask_id,
                message.concents.ForceSubtaskResultsResponse(
                    subtask_results_accepted=None,
                    subtask_results_rejected=(
                        message.tasks.SubtaskResultsRejected(
                            report_computed_task=(
                                self.msg.ack_report_computed_task
                                .report_computed_task),
                            force_get_task_result_failed=fgtrf,
                            reason=(message.tasks.SubtaskResultsRejected.REASON
                                    .ForcedResourcesFailure),
                        )
                    ),
                )
            )

    @mock.patch('golem.network.history.get')
    @mock.patch(
        'golem.network.concent.received_handler'
        '.TaskServerMessageHandler.'
        '_after_ack_report_computed_task')
    def test_positive_path(self, last_resort_mock, get_mock):
        get_mock.return_value = msg_factories \
            .tasks \
            .SubtaskResultsAcceptedFactory()
        library.interpret(self.msg)
        last_resort_mock.assert_not_called()
        self.task_server.client.concent_service.submit_task_message \
            .assert_called_once_with(
                get_mock().subtask_id,
                mock.ANY)


class SubtaskResultsVerifyTest(FileTransferTokenTestsBase,  # noqa pylint:disable=too-many-ancestors
                               FiletransfersTestBase):
    def setUp(self):
        super().setUp()
        self.task_server.keys_auth.ecc.raw_pubkey = \
            self.provider_keys.raw_pubkey

    def get_asrv(self, sign=True, **kwargs):
        provider_privkey = self.provider_keys.raw_privkey
        asrv_kwargs = {
            'subtask_results_verify__'
            'subtask_results_rejected__'
            'report_computed_task': self.rct
        }
        if sign:
            asrv_kwargs['subtask_results_verify__sign__privkey'] = \
                provider_privkey

        asrv_kwargs.update(kwargs)
        return msg_factories.concents.AckSubtaskResultsVerifyFactory(
            **asrv_kwargs
        )

    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.upload')
    def test_ack_subtask_results_verify(self, upload_mock):
        self.task_server.results_to_send[self.wtr.subtask_id] = self.wtr
        self.task_server.task_manager.comp_task_keeper.add_package_paths(
            self.wtr.task_id, [self.path])
        asrv = self.get_asrv()
        library.interpret(asrv)
        self.cft._run()
        self.cft._run()
        self.assertEqual(upload_mock.call_count, 2)
        resources_call, results_call = upload_mock.call_args_list

        self.assertEqual(resources_call[0][0].file_transfer_token,
                         asrv.file_transfer_token)
        self.assertEqual(resources_call[0][0].file_category,
                         FileTransferToken.FileInfo.Category.resources)

        self.assertEqual(results_call[0][0].file_transfer_token,
                         asrv.file_transfer_token)
        self.assertEqual(results_call[0][0].file_category,
                         FileTransferToken.FileInfo.Category.results)

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_ack_subtask_results_verify_no_ftt(self, log_mock):
        asrv = self.get_asrv(file_transfer_token=None)
        library.interpret(asrv)
        self.assertIn('File Transfer Token invalid', log_mock.call_args[0][0])

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_ack_subtask_results_verify_ftt_not_upload(self, log_mock):
        asrv = self.get_asrv(
            file_transfer_token__operation=FileTransferToken.Operation.download
        )
        library.interpret(asrv)
        self.assertIn('File Transfer Token invalid', log_mock.call_args[0][0])

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_ack_subtask_results_verify_srv_not_ours(self, log_mock):
        asrv = self.get_asrv(sign=False)
        library.interpret(asrv)
        self.assertIn('Signature invalid', log_mock.call_args[0][0])

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.upload')
    def test_ack_subtask_results_verify_no_results(
            self, upload_mock, log_mock):
        self.task_server.task_manager.comp_task_keeper.add_package_paths(
            self.wtr.task_id, [self.path])
        asrv = self.get_asrv()
        library.interpret(asrv)
        self.cft._run()
        self.cft._run()
        self.assertEqual(upload_mock.call_count, 1)
        self.assertIn('Cannot find the subtask', log_mock.call_args[0][0])

    @mock.patch('golem.network.concent.received_handler.logger.warning')
    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.upload')
    def test_ack_subtask_results_verify_no_resources(
            self, upload_mock, log_mock):
        self.task_server.results_to_send[self.wtr.subtask_id] = self.wtr
        asrv = self.get_asrv()
        library.interpret(asrv)
        self.cft._run()
        self.cft._run()
        self.assertEqual(upload_mock.call_count, 1)
        self.assertIn('Cannot upload resources', log_mock.call_args[0][0])


class SubtaskResultsSettledTest(TaskServerMessageHandlerTestBase):
    def setUp(self):
        super().setUp()
        self.client.transaction_system = mock.Mock()

    def test_settled(self):
        srs = msg_factories.concents.SubtaskResultsSettledFactory()
        self.task_server.client.node.key = srs.task_to_compute.provider_id

        library.interpret(srs)
        self.client.transaction_system.settle_income.assert_called_once_with(
            srs.task_to_compute.requestor_id,
            srs.subtask_id,
            srs.timestamp,
        )


class ForcePaymentTest(TaskServerMessageHandlerTestBase):
    @mock.patch('golem.network.concent.received_handler.logger.warning')
    def test_committed_requestor(self, log_mock):
        fpc = msg_factories.concents.ForcePaymentCommittedFactory.to_requestor()
        library.interpret(fpc)
        log_mock.assert_called_once()
        self.assertIn(
            "Our deposit was used to cover payment",
            log_mock.call_args[0][0],
        )

    @mock.patch('golem.network.concent.received_handler.logger.debug')
    def test_committed_provider(self, log_mock):
        fpc = msg_factories.concents.ForcePaymentCommittedFactory.to_provider(
            amount_pending=31337,
        )
        library.interpret(fpc)
        self.assertIn(
            "Forced payment from",
            log_mock.call_args[0][0],
        )

    @mock.patch('golem.network.concent.received_handler.logger.debug')
    def test_committed_unknown(self, _log_mock):
        fpc = msg_factories.concents.ForcePaymentCommittedFactory(
            amount_pending=31337,
            recipient_type=None,
        )
        with self.assertRaises(ValueError):
            library.interpret(fpc)
