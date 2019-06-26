# pylint: disable=protected-access, too-many-lines
import os
import time
from datetime import datetime, timedelta
import random
import tempfile
import uuid
from math import ceil
from unittest.mock import Mock, MagicMock, patch, ANY

from pydispatch import dispatcher
import freezegun

from golem_messages import factories as msg_factories
from golem_messages.datastructures import tasks as dt_tasks
from golem_messages.datastructures.masking import Mask
from golem_messages.factories.datastructures import p2p as dt_p2p_factory
from golem_messages.message import ComputeTaskDef
from golem_messages.utils import encode_hex as encode_key_id, pubkey_to_address
from requests import HTTPError

from golem import testutils
from golem.appconfig import AppConfig
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core import common
from golem.core.keysauth import KeysAuth
from golem.environments.environment import SupportStatus, UnsupportReason
from golem.network.hyperdrive.client import HyperdriveClientOptions, \
    HyperdriveClient, to_hyperg_peer
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resource import ResourceError
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager
from golem.task import tasksession
from golem.task.acl import DenyReason as AclDenyReason
from golem.task.result.resultmanager import EncryptedResultPackageManager
from golem.task.server import concent as server_concent
from golem.task.taskbase import AcceptClientVerdict
from golem.task.taskserver import (
    logger,
    TaskServer,
    WaitingTaskFailure,
    WaitingTaskResult,
)
from golem.task.taskstate import TaskState, TaskOp, TaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithreactor import TestDatabaseWithReactor

from tests.factories.hyperdrive import hyperdrive_client_kwargs


DEFAULT_RESOURCE_SIZE: int = 2 * 1024
DEFAULT_MAX_RESOURCE_SIZE_KB: int = 3
DEFAULT_ESTIMATED_MEMORY: int = 3 * 1024
DEFAULT_MAX_MEMORY_SIZE_KB: int = 4
DEFAULT_MIN_ACCEPTED_PERF: int = 77
DEFAULT_PROVIDER_PERF: int = 88


def get_example_task_header(
        key_id: str,
        resource_size: int = DEFAULT_RESOURCE_SIZE,
        estimated_memory: int = DEFAULT_ESTIMATED_MEMORY,
) -> dt_tasks.TaskHeader:
    requestor_public_key = encode_key_id(key_id)
    return msg_factories.datastructures.tasks.TaskHeaderFactory(
        mask=Mask().to_bytes(),
        requestor_public_key=requestor_public_key,
        task_owner=msg_factories.datastructures.p2p.Node(
            key=requestor_public_key,
            node_name="ABC",
            prv_port=40103,
            prv_addr='10.0.0.10',
            pub_port=40103,
            pub_addr='1.2.3.4',
        ),
        estimated_memory=estimated_memory,
    )


def get_mock_task(
        key_gen: str = "whatsoever",
        subtask_id: str = "whatever",
        resource_size: int = DEFAULT_RESOURCE_SIZE,
        estimated_memory: int = DEFAULT_ESTIMATED_MEMORY,
) -> Mock:
    task_mock = Mock()
    task_mock.header = get_example_task_header(
        key_gen,
        resource_size=resource_size,
        estimated_memory=estimated_memory,
    )
    task_id = task_mock.header.task_id
    task_mock.header.max_price = 1010
    task_mock.query_extra_data.return_value.ctd = ComputeTaskDef(
        task_id=task_id,
        subtask_id=subtask_id,
    )
    task_mock.should_accept_client.return_value = AcceptClientVerdict.ACCEPTED
    return task_mock


def _assert_log_msg(logger_mock, msg):
    assert len(logger_mock.output) == 1
    assert logger_mock.output[0].strip() == msg


class TaskServerTestBase(LogTestCase,
                         testutils.DatabaseFixture,
                         testutils.TestWithClient):

    @patch('golem.task.taskserver.NonHypervisedDockerCPUEnvironment')
    @patch('golem.network.concent.handlers_library.HandlersLibrary'
           '.register_handler')
    def setUp(self, *_):
        super().setUp()  # pylint: disable=arguments-differ
        random.seed()
        self.ccd = ClientConfigDescriptor()
        self.ccd.init_from_app_config(
            AppConfig.load_config(tempfile.mkdtemp(), 'cfg'))
        self.client.concent_service.enabled = False
        self.ts = TaskServer(
            node=dt_p2p_factory.Node(),
            config_desc=self.ccd,
            client=self.client,
            use_docker_manager=False,
        )
        self.ts.resource_manager.storage.get_dir.return_value = self.tempdir

    def tearDown(self):
        LogTestCase.tearDown(self)
        testutils.DatabaseFixture.tearDown(self)

        if hasattr(self, "ts") and self.ts:
            self.ts.quit()


class TestTaskServer(TaskServerTestBase):  # noqa pylint: disable=too-many-public-methods
    @patch('twisted.internet.task', create=True)
    @patch(
        'golem.network.concent.handlers_library.HandlersLibrary'
        '.register_handler',
    )
    @patch('golem.task.taskarchiver.TaskArchiver')
    @patch('golem.task.taskserver.NonHypervisedDockerCPUEnvironment')
    # pylint: disable=too-many-locals,too-many-statements
    def test_request(self, tar, *_):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 10
        n = dt_p2p_factory.Node()
        ts = TaskServer(
            node=n,
            config_desc=ccd,
            client=self.client,
            use_docker_manager=False,
            task_archiver=tar,
        )
        ts.verify_header_sig = lambda x: True
        self.ts = ts
        ts._is_address_accessible = Mock(return_value=True)
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        ts.client.get_requesting_trust.return_value = 0.3
        self.assertIsInstance(ts, TaskServer)
        self.assertIsNone(ts._request_random_task())

        keys_auth = KeysAuth(self.path, 'prv_key', '')
        task_header = get_example_task_header(keys_auth.public_key)
        task_id = task_header.task_id
        task_owner_key = task_header.task_owner.key  # pylint: disable=no-member
        self.ts.start_handshake(
            key_id=task_owner_key,
            task_id=task_id,
        )
        handshake = self.ts.resource_handshakes[task_owner_key]
        handshake.local_result = True
        handshake.remote_result = True
        self.ts.get_environment_by_id = Mock(return_value=None)
        self.ts.get_key_id = Mock(return_value='0'*128)
        self.ts.keys_auth.eth_addr = pubkey_to_address('0' * 128)
        ts.add_task_header(task_header)
        self.assertEqual(ts._request_random_task(), task_id)
        self.assertIn(task_id, ts.requested_tasks)
        assert ts.remove_task_header(task_id)
        self.assertNotIn(task_id, ts.requested_tasks)

        task_header = get_example_task_header(keys_auth.public_key)
        task_header.task_owner.pub_port = 0
        task_id2 = task_header.task_id
        self.assertTrue(ts.add_task_header(task_header))
        self.assertIsNotNone(ts.task_keeper.task_headers[task_id2])
        ts.remove_task_header(task_id2)

        # Task can be rejected for 3 reasons at this stage; in all cases
        # the task should be reported TaskArchiver listed as unsupported:
        # 1. Requestor's trust level is too low
        tar.reset_mock()
        ts.config_desc.requesting_trust = 0.5
        task_header = get_example_task_header(keys_auth.public_key)
        task_id3 = task_header.task_id
        ts.add_task_header(task_header)
        self.assertIsNone(ts._request_random_task())
        tar.add_support_status.assert_called_with(
            task_id3,
            SupportStatus(
                False,
                {UnsupportReason.REQUESTOR_TRUST: 0.3}))
        assert ts.remove_task_header(task_id3)

        # 2. Task's max price is too low
        tar.reset_mock()
        ts.config_desc.requesting_trust = 0.0
        task_header = get_example_task_header(keys_auth.public_key)
        task_id4 = task_header.task_id
        task_header.max_price = 1
        ts.add_task_header(task_header)
        self.assertIsNone(ts._request_random_task())
        tar.add_support_status.assert_called_with(
            task_id4,
            SupportStatus(
                False,
                {UnsupportReason.MAX_PRICE: 1}))
        assert ts.remove_task_header(task_id4)

        # 3. Requestor is on a black list.
        tar.reset_mock()
        ts.acl.disallow(keys_auth.key_id)
        task_header = get_example_task_header(keys_auth.public_key)
        task_id5 = task_header.task_id
        ts.add_task_header(task_header)
        self.assertIsNone(ts._request_random_task())
        tar.add_support_status.assert_called_with(
            task_id5,
            SupportStatus(
                False,
                {UnsupportReason.DENY_LIST: keys_auth.key_id}))
        assert ts.remove_task_header(task_id5)

    @patch(
        "golem.task.taskserver.TaskServer.should_accept_requestor",
        return_value=SupportStatus(True),
    )
    def test_request_task_concent_required(self, *_):
        self.ts.config_desc.min_price = 0
        self.ts.client.concent_service.enabled = True
        self.ts.task_archiver = Mock()
        self.ts._last_task_request_time = 0.0
        keys_auth = KeysAuth(self.path, 'prv_key', '')
        task_header = get_example_task_header(keys_auth.public_key)
        task_header.concent_enabled = False
        task_header.sign(private_key=keys_auth._private_key)
        self.ts.add_task_header(task_header)

        self.assertIsNone(self.ts._request_random_task())
        self.ts.task_archiver.add_support_status.assert_called_once_with(
            task_header.task_id,
            SupportStatus(
                False,
                {UnsupportReason.CONCENT_REQUIRED: True},
            ),
        )

    def test_change_config(self, *_):
        ts = self.ts

        ccd2 = ClientConfigDescriptor()
        ccd2.task_session_timeout = 124
        ccd2.min_price = 0.0057
        ccd2.task_request_interval = 31
        ts.change_config(ccd2)
        self.assertEqual(ts.config_desc, ccd2)
        self.assertEqual(ts.task_keeper.min_price, 0.0057)

    @patch("golem.task.taskserver.TaskServer._sync_pending")
    def test_sync(self, mock_sync_pending, *_):
        self.ts.sync_network()
        mock_sync_pending.assert_called_once_with()

    @patch("golem.task.taskserver.TaskServer._sync_pending",
           side_effect=RuntimeError("Intentional failure"))
    @patch("golem.task.server.concent.process_messages_received_from_concent")
    def test_sync_job_fails(self, *_):
        self.ts.sync_network()
        # Other jobs should be called even in case of failure of previous ones
        # pylint: disable=no-member
        server_concent.process_messages_received_from_concent\
            .assert_called_once()
        # pylint: enable=no-member

    def test_retry_sending_task_result(self, *_):
        ts = self.ts
        ts.network = Mock()

        subtask_id = 'xxyyzz'
        wtr = Mock()
        wtr.already_sending = True

        ts.results_to_send[subtask_id] = wtr

        ts.retry_sending_task_result(subtask_id)
        self.assertFalse(wtr.already_sending)

    @patch("golem.task.server.helpers.send_task_failure")
    @patch("golem.task.server.helpers.send_report_computed_task")
    def test_send_waiting_results(self, mock_send_rct, mock_send_tf, *_):
        ts = self.ts
        subtask_id = 'xxyyzz'

        wtr = WaitingTaskResult(
            task_id='task_id',
            subtask_id=subtask_id,
            result=['result'],
            last_sending_trial=0,
            delay_time=0,
            owner=dt_p2p_factory.Node(),
        )

        ts.results_to_send[subtask_id] = wtr

        wtr.already_sending = True

        ts._send_waiting_results()
        mock_send_rct.assert_not_called()

        wtr.last_sending_trial = 0
        ts.retry_sending_task_result(subtask_id)

        ts._send_waiting_results()
        mock_send_rct.assert_called_once_with(
            task_server=self.ts,
            waiting_task_result=wtr,
        )

        mock_send_rct.reset_mock()

        ts._send_waiting_results()
        mock_send_rct.assert_not_called()

        ts.results_to_send = {}

        wtf = WaitingTaskFailure(
            task_id="failed_task_id",
            subtask_id=subtask_id,
            owner=dt_p2p_factory.Node(),
            err_msg="Controlled failure",
        )

        ts.failures_to_send[subtask_id] = wtf
        ts._send_waiting_results()
        mock_send_tf.assert_called_once_with(
            waiting_task_failure=wtf,
        )
        self.assertEqual(ts.failures_to_send, {})

    def test_should_accept_provider_no_such_task(self, *_args):
        # given
        listener = Mock()
        dispatcher.connect(listener, signal='golem.taskserver')
        ts = self.ts
        node_id = "0xdeadbeef"
        node_name_id = common.short_node_id(node_id)
        task_id = "tid"

        ids = f'provider={node_name_id}, task_id={task_id}'

        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(
                node_id, "127.0.0.1", 'tid', 27.18, 1, 1)
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:Cannot find task in my tasks: {ids}')

        listener.assert_called_once_with(
            sender=ANY,
            signal='golem.taskserver',
            event='provider_rejected',
            node_id=node_id,
            task_id='tid',
            reason='not my task',
            details=None)

    def _prepare_env(self, *,
                     min_accepted_perf: int = DEFAULT_MIN_ACCEPTED_PERF) \
            -> None:
        env = Mock()
        env.get_min_accepted_performance.return_value = min_accepted_perf
        self.ts.get_environment_by_id = Mock(return_value=env)

    def test_should_accept_provider_insufficient_performance(self, *_args):
        # given
        listener = Mock()
        dispatcher.connect(listener, signal='golem.taskserver')
        provider_perf = DEFAULT_MIN_ACCEPTED_PERF - 10

        ts = self.ts
        node_id = "0xdeadbeef"
        node_name_id = common.short_node_id(node_id)

        task = get_mock_task()
        task_id = task.header.task_id
        ts.task_manager.tasks[task_id] = task

        self._prepare_env()

        ids = f'provider={node_name_id}, task_id={task_id}'

        with self.assertLogs(logger, level='INFO') as cm:
            # when
            accepted = ts.should_accept_provider(
                node_id, "127.0.0.1", task_id,
                provider_perf,
                DEFAULT_MAX_MEMORY_SIZE_KB, 1)

            # then
            assert not accepted
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:insufficient provider performance: '
                f'{provider_perf} < {DEFAULT_MIN_ACCEPTED_PERF}; {ids}')

        listener.assert_called_once_with(
            sender=ANY,
            signal='golem.taskserver',
            event='provider_rejected',
            node_id=node_id,
            task_id=task_id,
            reason='performance',
            details={
                'provider_perf': provider_perf,
                'min_accepted_perf': DEFAULT_MIN_ACCEPTED_PERF,
            })

    def test_should_accept_provider_insufficient_memory_size(self, *_args):
        # given
        listener = Mock()
        dispatcher.connect(listener, signal='golem.taskserver')
        estimated_memory = DEFAULT_MAX_MEMORY_SIZE_KB*1024 + 1

        ts = self.ts
        node_id = "0xdeadbeef"
        node_name_id = common.short_node_id(node_id)

        task = get_mock_task(estimated_memory=estimated_memory)
        task_id = task.header.task_id
        ts.task_manager.tasks[task_id] = task

        self._prepare_env()

        ids = f'provider={node_name_id}, task_id={task_id}'

        with self.assertLogs(logger, level='INFO') as cm:
            # when
            accepted = ts.should_accept_provider(
                node_id, "127.0.0.1", task_id, DEFAULT_PROVIDER_PERF,
                DEFAULT_MAX_RESOURCE_SIZE_KB, DEFAULT_MAX_MEMORY_SIZE_KB)

            # then
            assert not accepted
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:insufficient provider memory size: '
                f'{estimated_memory} B < {DEFAULT_MAX_MEMORY_SIZE_KB} '
                f'KiB; {ids}')

        listener.assert_called_once_with(
            sender=ANY,
            signal='golem.taskserver',
            event='provider_rejected',
            node_id=node_id,
            task_id=task_id,
            reason='memory size',
            details={
                'memory_size': estimated_memory,
                'max_memory_size': DEFAULT_MAX_MEMORY_SIZE_KB*1024
            })

    def test_should_accept_provider_insufficient_trust(self, *_args):
        # given
        listener = Mock()
        dispatcher.connect(listener, signal='golem.taskserver')
        ts = self.ts
        node_id = "0xdeadbeef"
        node_name_id = common.short_node_id(node_id)

        task = get_mock_task()
        task_id = task.header.task_id
        ts.task_manager.tasks[task_id] = task

        self._prepare_env()

        self.client.get_computing_trust = Mock()

        ids = f'provider={node_name_id}, task_id={task_id}'

        ts.config_desc.computing_trust = 0.4

        # given
        self.client.get_computing_trust.return_value = \
            ts.config_desc.computing_trust + 0.2
        # when/then
        assert ts.should_accept_provider(
            node_id, "127.0.0.1", task_id, DEFAULT_PROVIDER_PERF,
            DEFAULT_MAX_RESOURCE_SIZE_KB, DEFAULT_MAX_MEMORY_SIZE_KB)

        # given
        self.client.get_computing_trust.return_value = \
            ts.config_desc.computing_trust
        # when/then
        assert ts.should_accept_provider(
            node_id, "127.0.0.1", task_id, DEFAULT_PROVIDER_PERF,
            DEFAULT_MAX_RESOURCE_SIZE_KB, DEFAULT_MAX_MEMORY_SIZE_KB)

        # given
        trust = ts.config_desc.computing_trust - 0.2
        self.client.get_computing_trust.return_value = trust
        with self.assertLogs(logger, level='INFO') as cm:
            # when
            accepted = ts.should_accept_provider(
                node_id, "127.0.0.1", task_id, DEFAULT_PROVIDER_PERF,
                DEFAULT_MAX_RESOURCE_SIZE_KB, DEFAULT_MAX_MEMORY_SIZE_KB)

            # then
            assert not accepted
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:insufficient provider trust level:'
                f' 0.2 < 0.4; {ids}')

        listener.assert_called_once_with(
            sender=ANY,
            signal='golem.taskserver',
            event='provider_rejected',
            node_id=node_id,
            task_id=task_id,
            reason='trust',
            details={
                'trust': trust,
                'required_trust': ts.config_desc.computing_trust,
            })

    def test_should_accept_provider_masking(self, *_args):
        # given
        listener = Mock()
        dispatcher.connect(listener, signal='golem.taskserver')
        ts = self.ts
        node_id = "0xdeadbeef"
        node_name_id = common.short_node_id(node_id)

        task = get_mock_task()
        task_id = task.header.task_id
        ts.task_manager.tasks[task_id] = task

        self._prepare_env()

        self.client.get_computing_trust = Mock(return_value=0)

        task.header.mask = Mask(b'\xff' * Mask.MASK_BYTES)

        ids = f'provider={node_name_id}, task_id={task_id}'

        with self.assertLogs(logger, level='INFO') as cm:
            # when
            accepted = ts.should_accept_provider(
                node_id, "127.0.0.1", task_id, DEFAULT_PROVIDER_PERF,
                DEFAULT_MAX_RESOURCE_SIZE_KB, DEFAULT_MAX_MEMORY_SIZE_KB)

            # then
            assert not accepted
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:network mask mismatch: {ids}')

        listener.assert_called_once_with(
            sender=ANY,
            signal='golem.taskserver',
            event='provider_rejected',
            node_id=node_id,
            task_id=task_id,
            reason='netmask',
            details=None)

    def test_should_accept_provider_rejected(self, *_args):
        # given
        listener = Mock()
        dispatcher.connect(listener, signal='golem.taskserver')
        ts = self.ts
        node_id = "0xdeadbeef"

        task = get_mock_task()
        task_id = task.header.task_id
        ts.task_manager.tasks[task_id] = task

        self._prepare_env()

        self.client.get_computing_trust = Mock(return_value=0)
        task.header.mask = Mask()
        task.should_accept_client.return_value = AcceptClientVerdict.REJECTED

        with self.assertLogs(logger, level='INFO') as cm:
            # when
            accepted = ts.should_accept_provider(node_id, "127.0.0.1",
                                                 task_id, 99, 3, 4)

            # then
            assert not accepted
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:provider {node_id}'
                f' is not allowed for this task at this moment'
                f' (either waiting for results or previously failed)'
            )

        listener.assert_called_once_with(
            sender=ANY,
            signal='golem.taskserver',
            event='provider_rejected',
            node_id=node_id,
            task_id=task_id,
            reason='not accepted',
            details={
                'verdict': AcceptClientVerdict.REJECTED.value,
            })

    def test_should_accept_provider_acl(self, *_args):
        # given
        listener = Mock()
        dispatcher.connect(listener, signal='golem.taskserver')
        ts = self.ts
        node_id = "0xdeadbeef"
        node_name_id = common.short_node_id(node_id)

        task = get_mock_task()
        task_id = task.header.task_id
        ts.task_manager.tasks[task_id] = task

        self._prepare_env()

        self.client.get_computing_trust = Mock(return_value=0)

        ids = f'provider={node_name_id}, task_id={task_id}'

        # given
        task.header.mask = Mask()
        ts.acl.disallow(node_id)
        # then
        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(
                node_id=node_id,
                address="127.0.0.1",
                task_id=task_id,
                provider_perf=DEFAULT_PROVIDER_PERF,
                max_resource_size=DEFAULT_MAX_RESOURCE_SIZE_KB,
                max_memory_size=DEFAULT_MAX_MEMORY_SIZE_KB,
            )
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:provider is blacklisted; {ids}')

        listener.assert_called_once_with(
            sender=ANY,
            signal='golem.taskserver',
            event='provider_rejected',
            node_id=node_id,
            task_id=task_id,
            reason='acl',
            details={'acl_reason': AclDenyReason.blacklisted.value})
        listener.reset_mock()

        # given
        ts.acl_ip.disallow("127.0.0.1")
        # then
        assert not ts.should_accept_provider(
            "XYZ", "127.0.0.1", task_id, DEFAULT_PROVIDER_PERF,
            DEFAULT_MAX_RESOURCE_SIZE_KB, DEFAULT_MAX_MEMORY_SIZE_KB)
        listener.assert_called_once_with(
            sender=ANY,
            signal='golem.taskserver',
            event='provider_rejected',
            node_id="XYZ",
            task_id=task_id,
            reason='acl',
            details={'acl_reason': AclDenyReason.blacklisted.value})

    def test_should_accept_requestor(self, *_):
        ts = self.ts
        self.client.get_requesting_trust = Mock(return_value=0.4)
        ts.config_desc.requesting_trust = 0.2
        assert ts.should_accept_requestor("ABC").is_ok()
        ts.config_desc.requesting_trust = 0.4
        assert ts.should_accept_requestor("ABC").is_ok()
        ts.config_desc.requesting_trust = 0.5
        ss = ts.should_accept_requestor("ABC")
        assert not ss.is_ok()
        assert UnsupportReason.REQUESTOR_TRUST in ss.desc
        self.assertEqual(ss.desc[UnsupportReason.REQUESTOR_TRUST], 0.4)

        ts.config_desc.requesting_trust = 0.2
        assert ts.should_accept_requestor("ABC").is_ok()

        ts.acl.disallow("ABC")
        ss = ts.should_accept_requestor("ABC")
        assert not ss.is_ok()
        assert UnsupportReason.DENY_LIST in ss.desc
        self.assertEqual(ss.desc[UnsupportReason.DENY_LIST], "ABC")

    def test_new_connection(self, *_):
        ts = self.ts
        tss = tasksession.TaskSession(Mock())
        ts.new_connection(tss)
        assert len(ts.task_sessions_incoming) == 1
        assert ts.task_sessions_incoming.pop() == tss

    def test_download_options(self, *_):
        dm = DirManager(self.path)
        rm = HyperdriveResourceManager(dm, **hyperdrive_client_kwargs())  # noqa pylint: disable=unexpected-keyword-arg
        self.client.resource_server.resource_manager = rm
        ts = self.ts

        options = HyperdriveClientOptions(HyperdriveClient.CLIENT_ID,
                                          HyperdriveClient.VERSION)

        client_options = ts.get_download_options(options)
        assert client_options.peers is None

        peers = [
            to_hyperg_peer('127.0.0.1', 3282),
            to_hyperg_peer('127.0.0.1', 0),
            to_hyperg_peer('127.0.0.1', None),
            to_hyperg_peer('1.2.3.4', 3282),
            {'uTP': ('1.2.3.4', 3282)}
        ]

        options = HyperdriveClientOptions(HyperdriveClient.CLIENT_ID,
                                          HyperdriveClient.VERSION,
                                          options=dict(peers=peers))

        client_options = ts.get_download_options(options, size=1024)
        assert client_options.options.get('peers') == [
            to_hyperg_peer('127.0.0.1', 3282),
            to_hyperg_peer('1.2.3.4', 3282),
        ]
        assert client_options.options.get('size') == 1024

    def test_download_options_errors(self, *_):
        built_options = Mock()
        self.ts.resource_manager.build_client_options\
            .return_value=built_options

        self.assertIs(
            self.ts.get_download_options(received_options=None),
            built_options,
        )

        assert self.ts.get_download_options(
            received_options={'options': {'peers': ['Invalid']}},
        ) is built_options

        assert self.ts.get_download_options(
            received_options=Mock(filtered=Mock(side_effect=Exception)),
        ) is built_options

    def test_pause_and_resume(self, *_):
        from apps.core.task.coretask import CoreTask

        assert self.ts.active
        assert not CoreTask.VERIFICATION_QUEUE._paused

        self.ts.pause()

        assert not self.ts.active
        assert CoreTask.VERIFICATION_QUEUE._paused

        self.ts.resume()

        assert self.ts.active
        assert not CoreTask.VERIFICATION_QUEUE._paused


class TaskServerTaskHeaderTest(TaskServerTestBase):
    def test_add_task_header(self, *_):
        keys_auth_2 = KeysAuth(
            os.path.join(self.path, "2"),
            'priv_key',
            'password',
        )

        ts = self.ts

        task_header = get_example_task_header(keys_auth_2.public_key)

        self.assertFalse(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 0)

        task_header.sign(private_key=keys_auth_2._private_key)  # noqa pylint:disable=no-value-for-parameter

        self.assertTrue(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 1)

        task_header = get_example_task_header(keys_auth_2.public_key)
        task_header.sign(private_key=keys_auth_2._private_key)  # noqa pylint:disable=no-value-for-parameter

        self.assertTrue(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 2)

        self.assertTrue(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 2)

    def test_add_task_header_past_deadline(self):
        keys_auth_2 = KeysAuth(
            os.path.join(self.path, "2"),
            'priv_key',
            'password',
        )

        ts = self.ts

        with freezegun.freeze_time(datetime.utcnow() - timedelta(hours=2)):
            task_header = get_example_task_header(keys_auth_2.public_key)
            task_header.sign(private_key=keys_auth_2._private_key)  # noqa pylint:disable=no-value-for-parameter

        self.assertFalse(ts.add_task_header(task_header))


class TaskServerBase(TestDatabaseWithReactor, testutils.TestWithClient):
    def setUp(self):
        for parent in TaskServerBase.__bases__:
            parent.setUp(self)
        random.seed()
        self.ccd = self._get_config_desc()
        with patch('golem.network.concent.handlers_library.HandlersLibrary'
                   '.register_handler',):
            self.ts = TaskServer(
                node=dt_p2p_factory.Node(),
                config_desc=self.ccd,
                client=self.client,
                use_docker_manager=False,
            )
        self.ts.task_computer = MagicMock()

    def tearDown(self):
        for parent in TaskServerBase.__bases__:
            parent.tearDown(self)

    def _get_config_desc(self):
        ccd = ClientConfigDescriptor()
        ccd.root_path = self.path
        ccd.max_memory_size = 1024 * 1024  # 1 GiB
        ccd.num_cores = 1
        return ccd


# pylint: disable=too-many-ancestors
class TestTaskServer2(TaskServerBase):

    @patch('golem.task.taskmanager.TaskManager._get_task_output_dir')
    @patch("golem.task.taskmanager.TaskManager.dump_task")
    @patch("golem.task.taskserver.Trust")
    def test_results(self, trust, *_):
        ts = self.ts

        task_mock = get_mock_task(key_gen="xyz", subtask_id="xxyyzz")
        task_mock.get_trust_mod.return_value = ts.max_trust
        task_id = task_mock.header.task_id
        extra_data = Mock()
        extra_data.ctd = ComputeTaskDef()
        extra_data.ctd['task_id'] = task_mock.header.task_id
        extra_data.ctd['subtask_id'] = "xxyyzz"
        task_mock.query_extra_data.return_value = extra_data
        task_mock.task_definition.subtask_timeout = 3600
        task_mock.should_accept_client.return_value = \
            AcceptClientVerdict.ACCEPTED

        ts.task_manager.keys_auth._private_key = b'a' * 32
        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states[task_id].status = TaskStatus.computing
        subtask = ts.task_manager.get_next_subtask(
            "DEF",
            task_id,
            1000, 10,
            5, 10)
        assert subtask is not None
        expected_value = ceil(1031 * 1010 / 3600)
        prev_calls = trust.COMPUTED.increase.call_count
        ts.accept_result("xxyyzz", "key", "eth_address", expected_value)
        ts.client.transaction_system.add_payment_info.assert_called_with(
            subtask_id="xxyyzz",
            value=expected_value,
            eth_address="eth_address",
            node_id=task_mock.header.task_owner.key,  # pylint: disable=no-member
            task_id=task_mock.header.task_id,
        )
        self.assertGreater(trust.COMPUTED.increase.call_count, prev_calls)

    def test_disconnect(self, *_):
        session_mock = Mock()
        self.ts.sessions['active_node_id'] = session_mock
        self.ts.sessions['pending_node_id'] = None
        self.ts.disconnect()
        session_mock.dropped.assert_called_once_with()


# pylint: disable=too-many-ancestors
class TestSubtaskWaiting(TaskServerBase):

    def test_requested_tasks(self, *_):
        task_id = str(uuid.uuid4())
        subtask_id = str(uuid.uuid4())
        self.ts.requested_tasks.add(task_id)
        self.ts.subtask_waiting(task_id, subtask_id)
        self.assertNotIn(task_id, self.ts.requested_tasks)


class TestRestoreResources(LogTestCase, testutils.DatabaseFixture,
                           testutils.TestWithClient):

    @patch('golem.task.taskserver.NonHypervisedDockerCPUEnvironment')
    def setUp(self, _):
        for parent in self.__class__.__bases__:
            parent.setUp(self)

        self.node = dt_p2p_factory.Node(
            prv_addr='10.0.0.2',
            prv_port=40102,
            pub_addr='1.2.3.4',
            pub_port=40102,
            prv_addresses=['10.0.0.2'],
        )

        self.resource_manager = Mock(
            add_resources=Mock(side_effect=lambda *a, **b: ([], "a1b2c3"))
        )
        with patch('golem.network.concent.handlers_library.HandlersLibrary'
                   '.register_handler',):
            self.ts = TaskServer(
                node=self.node,
                config_desc=ClientConfigDescriptor(),
                client=self.client,
                use_docker_manager=False,
            )
        self.ts.task_manager.notify_update_task = Mock(
            side_effect=self.ts.task_manager.notify_update_task
        )
        self.ts.task_manager.delete_task = Mock(
            side_effect=self.ts.task_manager.delete_task
        )
        self.ts.client.resource_server.resource_manager = self.resource_manager
        self.ts.task_manager.dump_task = Mock()
        self.task_count = 3

    @staticmethod
    def _create_tasks(task_server, count):
        for _ in range(count):
            task_id = str(uuid.uuid4())
            task = Mock()
            task.header.deadline = 2524608000
            task.get_resources.return_value = []
            task_server.task_manager.tasks[task_id] = task
            task_server.task_manager.tasks_states[task_id] = TaskState()

    def test_without_tasks(self, *_):
        with patch.object(self.resource_manager, 'add_resources',
                          side_effect=ConnectionError):
            self.ts.restore_resources()
            assert not self.resource_manager.add_resources.called
            assert not self.ts.task_manager.delete_task.called
            assert not self.ts.task_manager.notify_update_task.called

    def test_with_connection_error(self, *_):
        self._create_tasks(self.ts, self.task_count)

        with patch.object(self.resource_manager, 'add_resources',
                          side_effect=ConnectionError):
            self.ts.restore_resources()
            assert self.resource_manager.add_resources.call_count == \
                self.task_count
            assert self.ts.task_manager.delete_task.call_count == \
                self.task_count
            assert not self.ts.task_manager.notify_update_task.called

    def test_with_http_error(self, *_):
        self._create_tasks(self.ts, self.task_count)

        with patch.object(self.resource_manager, 'add_resources',
                          side_effect=HTTPError):
            self.ts.restore_resources()
            assert self.resource_manager.add_resources.call_count == \
                self.task_count
            assert self.ts.task_manager.delete_task.call_count == \
                self.task_count
            assert not self.ts.task_manager.notify_update_task.called

    def test_with_http_error_and_resource_hashes(self, *_):
        self._test_with_error_and_resource_hashes(HTTPError)

    def test_with_resource_error_and_resource_hashes(self, *_):
        self._test_with_error_and_resource_hashes(ResourceError)

    def _test_with_error_and_resource_hashes(self, error_class):
        self._create_tasks(self.ts, self.task_count)
        for state in self.ts.task_manager.tasks_states.values():
            state.resource_hash = str(uuid.uuid4())

        with patch.object(self.resource_manager, 'add_resources',
                          side_effect=error_class):
            self.ts.restore_resources()
            assert self.resource_manager.add_resources.call_count ==\
                self.task_count * 2
            assert self.ts.task_manager.delete_task.call_count == \
                self.task_count
            assert not self.ts.task_manager.notify_update_task.called

    def test_restore_resources(self, *_):
        self._create_tasks(self.ts, self.task_count)

        self.ts.restore_resources()
        assert self.resource_manager.add_resources.call_count == self.task_count
        assert not self.ts.task_manager.delete_task.called
        assert self.ts.task_manager.notify_update_task.call_count == \
            self.task_count

    def test_restore_resources_call(self, *_):
        self._create_tasks(self.ts, 1)

        task_states = self.ts.task_manager.tasks_states
        task_id = next(iter(task_states.keys()))
        task_state = next(iter(task_states.values()))
        task_state.package_path = os.path.join(self.path, task_id + '.bin')
        task_state.resource_hash = str(uuid.uuid4())

        self.ts._restore_resources = Mock()
        self.ts.restore_resources()

        self.ts._restore_resources.assert_called_with(
            [task_state.package_path], task_id,
            resource_hash=task_state.resource_hash, timeout=ANY
        )

    def test_finished_task_listener(self, *_):
        self.ts.client = Mock()
        remove_task = self.ts.client.p2pservice.remove_task
        remove_task_funds_lock = self.ts.client.funds_locker.remove_task

        values = dict(TaskOp.__members__)
        values.pop('FINISHED')
        values.pop('TIMEOUT')

        for value in values:
            self.ts.finished_task_listener(op=value)
            assert not remove_task.called

        for value in values:
            self.ts.finished_task_listener(event='task_status_updated',
                                           op=value)
            assert not remove_task.called

        self.ts.finished_task_listener(event='task_status_updated',
                                       op=TaskOp.FINISHED)
        assert remove_task.called
        assert remove_task_funds_lock.called

        self.ts.finished_task_listener(event='task_status_updated',
                                       op=TaskOp.TIMEOUT)
        assert remove_task.call_count == 2
        assert remove_task_funds_lock.call_count == 2


class TestSendResults(TaskServerTestBase):

    def test_wrong_result_format(self):
        with self.assertRaises(AttributeError):
            self.ts.send_results('subtask_id', 'task_id', {'foo': 'bar'})

    def test_subtask_already_sent(self):
        self.ts.results_to_send['subtask_id'] = Mock(spec=WaitingTaskResult)
        with self.assertRaises(RuntimeError):
            self.ts.send_results('subtask_id', 'task_id', {'data': 'data'})

    @patch('golem.task.taskserver.Trust')
    def test_ok(self, trust):
        result_secret = Mock()
        result_hash = Mock()
        result_path = Mock()
        package_sha1 = Mock()
        package_size = Mock()
        package_path = Mock()

        result_manager = Mock(spec=EncryptedResultPackageManager)
        result_manager.gen_secret.return_value = result_secret
        result_manager.create.return_value = (
            result_hash,
            result_path,
            package_sha1,
            package_size,
            package_path
        )

        header = MagicMock()
        self.ts.task_keeper.task_headers['task_id'] = header

        with patch.object(
            self.ts.task_manager, 'task_result_manager', result_manager
        ):
            self.ts.send_results('subtask_id', 'task_id', {'data': 'data'})

        result = self.ts.results_to_send.get('subtask_id')
        self.assertIsInstance(result, WaitingTaskResult)
        self.assertEqual(result.task_id, 'task_id')
        self.assertEqual(result.subtask_id, 'subtask_id')
        self.assertEqual(result.result, 'data')
        self.assertEqual(result.last_sending_trial, 0)
        self.assertEqual(result.delay_time, 0)
        self.assertEqual(result.owner, header.task_owner)
        self.assertEqual(result.result_secret, result_secret)
        self.assertEqual(result.result_hash, result_hash)
        self.assertEqual(result.result_path, result_path)
        self.assertEqual(result.package_sha1, package_sha1)
        self.assertEqual(result.result_size, package_size)
        self.assertEqual(result.package_path, package_path)

        trust.REQUESTED.increase.assert_called_once_with(header.task_owner.key)


@patch('golem.task.taskcomputer.TaskComputer.has_assigned_task')
@patch('golem.task.taskcomputer.TaskComputer.task_given')
@patch('golem.task.taskserver.TaskServer.request_resource')
@patch('golem.task.taskserver.update_requestor_assigned_sum')
@patch('golem.task.taskserver.dispatcher')
@patch('golem.task.taskserver.logger')
class TestTaskGiven(TaskServerTestBase):
    # pylint: disable=too-many-arguments

    def test_ok(
            self, logger_mock, dispatcher_mock, update_requestor_assigned_sum,
            request_resource, task_given, has_assigned_task):

        has_assigned_task.return_value = False
        node_id = 'test_node'
        task_id = 'test_task'
        subtask_id = 'test_subtask'
        resources = ['test_resource']
        ctd = ComputeTaskDef(
            task_id=task_id,
            subtask_id=subtask_id,
            resources=resources
        )
        price = 123

        result = self.ts.task_given(node_id, ctd, price)
        self.assertEqual(result, True)

        task_given.assert_called_once_with(ctd)
        request_resource.assert_called_once_with(task_id, subtask_id, resources)
        update_requestor_assigned_sum.assert_called_once_with(node_id, price)
        dispatcher_mock.send.assert_called_once_with(
            signal='golem.subtask',
            event='started',
            subtask_id=subtask_id,
            price=price
        )
        logger_mock.error.assert_not_called()

    def test_already_assigned(
            self, logger_mock, dispatcher_mock, update_requestor_assigned_sum,
            request_resource, task_given, has_assigned_task):

        has_assigned_task.return_value = True
        result = self.ts.task_given('', Mock(), 0)
        self.assertEqual(result, False)

        task_given.assert_not_called()
        request_resource.assert_not_called()
        update_requestor_assigned_sum.assert_not_called()
        dispatcher_mock.send.assert_not_called()
        logger_mock.error.assert_called()


@patch('golem.task.taskserver.logger')
@patch('golem.task.taskcomputer.TaskComputer.start_computation')
class TestResourceCollected(TaskServerTestBase):

    def test_wrong_task_id(self, start_computation, logger_mock):
        self.ts.task_computer.assigned_subtask = ComputeTaskDef(task_id='test')
        result = self.ts.resource_collected('wrong_id')
        self.assertFalse(result)
        logger_mock.error.assert_called_once()
        start_computation.assert_not_called()

    def test_ok(self, start_computation, logger_mock):
        self.ts.task_computer.assigned_subtask = ComputeTaskDef(task_id='test')
        result = self.ts.resource_collected('test')
        self.assertTrue(result)
        logger_mock.error.assert_not_called()
        start_computation.assert_called_once_with()


@patch('golem.task.taskserver.logger')
@patch('golem.task.taskserver.TaskServer.send_task_failed')
@patch('golem.task.taskcomputer.TaskComputer.task_interrupted')
class TestResourceFailure(TaskServerTestBase):

    def test_wrong_task_id(self, interrupted, send_task_failed, logger_mock):
        self.ts.task_computer.assigned_subtask = ComputeTaskDef(task_id='test')
        self.ts.resource_failure('wrong_id', 'reason')
        logger_mock.error.assert_called_once()
        interrupted.assert_not_called()
        send_task_failed.assert_not_called()

    def test_ok(self, interrupted, send_task_failed, logger_mock):
        self.ts.task_computer.assigned_subtask = ComputeTaskDef(
            task_id='test_task', subtask_id='test_subtask'
        )
        self.ts.resource_failure('test_task', 'test_reason')
        logger_mock.error.assert_not_called()
        interrupted.assert_called_once_with()
        send_task_failed.assert_called_once_with(
            'test_subtask',
            'test_task',
            'Error downloading resources: test_reason'
        )


class TestRequestRandomTask(TaskServerTestBase):

    def setUp(self):
        super().setUp()
        self.ts.task_computer = MagicMock()
        self.ts.task_keeper = MagicMock()

    def test_task_already_assigned(self):
        self.ts.task_computer.has_assigned_task.return_value = True
        self.ts.task_computer.compute_tasks = True
        self.ts.task_computer.runnable = True

        self.assertIsNone(self.ts._request_random_task())

    def test_task_computer_not_accepting_tasks(self):
        self.ts.task_computer.has_assigned_task.return_value = False
        self.ts.task_computer.compute_tasks = False
        self.ts.task_computer.runnable = True

        self.assertIsNone(self.ts._request_random_task())

    def test_task_computer_not_runnable(self):
        self.ts.task_computer.has_assigned_task.return_value = False
        self.ts.task_computer.compute_tasks = True
        self.ts.task_computer.runnable = False

        self.assertIsNone(self.ts._request_random_task())

    @freezegun.freeze_time()
    def test_request_interval(self):
        self.ts.task_computer.has_assigned_task.return_value = False
        self.ts.task_computer.compute_tasks = True
        self.ts.task_computer.runnable = True
        self.ts.config_desc.task_request_interval = 1.0
        self.ts._last_task_request_time = time.time()

        self.assertIsNone(self.ts._request_random_task())

    @freezegun.freeze_time()
    def test_no_supported_tasks_in_task_keeper(self):
        self.ts.task_computer.has_assigned_task.return_value = False
        self.ts.task_computer.compute_tasks = True
        self.ts.task_computer.runnable = True
        self.ts.config_desc.task_request_interval = 1.0
        self.ts._last_task_request_time = time.time() - 1.0
        self.ts.task_keeper.get_task.return_value = None

        self.assertIsNone(self.ts._request_random_task())

    @freezegun.freeze_time()
    @patch('golem.task.taskserver.TaskServer._request_task')
    def test_ok(self, request_task):
        self.ts.task_computer.has_assigned_task.return_value = False
        self.ts.task_computer.compute_tasks = True
        self.ts.task_computer.runnable = True
        self.ts.config_desc.task_request_interval = 1.0
        self.ts._last_task_request_time = time.time() - 1.0
        task_header = Mock()
        self.ts.task_keeper.get_task.return_value = task_header

        result = self.ts._request_random_task()
        self.assertEqual(result, request_task.return_value)
        self.assertEqual(self.ts._last_task_request_time, time.time())
        self.ts.task_computer.stats.increase_stat.assert_called_once_with(
            'tasks_requested')
        request_task.assert_called_once_with(task_header)
