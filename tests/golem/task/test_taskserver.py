# pylint: disable=protected-access, too-many-lines
import asyncio
import os
import time
from datetime import datetime, timedelta
import random
import tempfile
import uuid
from math import ceil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, ANY, call

from pydispatch import dispatcher
import freezegun
from twisted.internet import defer
from twisted.trial.unittest import TestCase as TwistedTestCase

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
from golem.core.common import install_reactor
from golem.core.keysauth import KeysAuth
from golem.environments.environment import (
    Environment as OldEnv,
    SupportStatus,
    UnsupportReason,
)
from golem.envs import Environment as NewEnv
from golem.envs.docker.cpu import DockerCPUEnvironment
from golem.network.hyperdrive.client import HyperdriveClientOptions, \
    HyperdriveClient, to_hyperg_peer
from golem.resource import resourcemanager
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resource import ResourceError
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager
from golem.resource.resourcemanager import ResourceManager
from golem.task import tasksession
from golem.task.acl import DenyReason as AclDenyReason, AclRule
from golem.task.benchmarkmanager import BenchmarkManager
from golem.task.result.resultmanager import EncryptedResultPackageManager
from golem.task.server import concent as server_concent
from golem.task.taskarchiver import TaskArchiver
from golem.task.taskbase import AcceptClientVerdict
from golem.task.taskkeeper import TaskHeaderKeeper, CompTaskKeeper, CompTaskInfo
from golem.task.taskmanager import TaskManager
from golem.task.taskserver import (
    logger,
    TaskServer,
    WaitingTaskFailure,
    WaitingTaskResult,
)
from golem.task.taskstate import TaskState, TaskOp, TaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithreactor import TestDatabaseWithReactor, \
    uninstall_reactor

from tests.factories.hyperdrive import hyperdrive_client_kwargs
from tests.golem.envs.localhost import LocalhostEnvironment, LocalhostConfig, \
    LocalhostPrerequisites, LocalhostPayloadBuilder

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

    @patch('golem.network.concent.handlers_library.HandlersLibrary'
           '.register_handler')
    @patch('golem.task.taskserver.TaskComputerAdapter')
    @patch('golem.task.taskserver.NonHypervisedDockerCPUEnvironment')
    def setUp(self, docker_env, *_):  # pylint: disable=arguments-differ
        super().setUp()
        random.seed()
        self.ccd = ClientConfigDescriptor()
        self.ccd.init_from_app_config(
            AppConfig.load_config(tempfile.mkdtemp(), 'cfg'))
        self.client.concent_service.enabled = False
        self.client.keys_auth.key_id = 'key_id'
        self.client.keys_auth.eth_addr = 'eth_addr'
        docker_env().metadata.return_value.id = DockerCPUEnvironment.ENV_ID
        self.ts = TaskServer(
            node=dt_p2p_factory.Node(),
            config_desc=self.ccd,
            client=self.client,
            use_docker_manager=False,
            task_archiver=Mock(spec=TaskArchiver)
        )
        self.ts.resource_manager.storage.get_dir.return_value = self.tempdir

    def tearDown(self):
        LogTestCase.tearDown(self)
        testutils.DatabaseFixture.tearDown(self)

        if hasattr(self, "ts") and self.ts:
            self.ts.quit()

    def _prepare_handshake(self, task_owner_key, task_id):
        self.ts.start_handshake(
            key_id=task_owner_key,
            task_id=task_id,
        )
        handshake = self.ts.resource_handshakes[task_owner_key]
        handshake.local_result = True
        handshake.remote_result = True

    def _prepare_keys_auth(self):
        self.ts.keys_auth.key_id = '0'*128
        self.ts.keys_auth.eth_addr = pubkey_to_address('0' * 128)

    def _prepare_env(self, *,
                     min_accepted_perf: int = DEFAULT_MIN_ACCEPTED_PERF) \
            -> None:
        env = Mock(spec=OldEnv)
        env.get_min_accepted_performance.return_value = min_accepted_perf
        env.get_performance = Mock(return_value=0.0)
        self.ts.get_environment_by_id = Mock(return_value=env)


class TestTaskServer(TaskServerTestBase):  # noqa pylint: disable=too-many-public-methods
    @patch('twisted.internet.task', create=True)
    @patch(
        'golem.network.concent.handlers_library.HandlersLibrary'
        '.register_handler',
    )
    @patch('golem.task.taskarchiver.TaskArchiver')
    @patch('golem.task.taskserver.NonHypervisedDockerCPUEnvironment')
    # pylint: disable=too-many-locals,too-many-statements
    def test_request(self, docker_env, tar, *_):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 10
        n = dt_p2p_factory.Node()
        docker_env().metadata.return_value.id = DockerCPUEnvironment.ENV_ID
        ts = TaskServer(
            node=n,
            config_desc=ccd,
            client=self.client,
            use_docker_manager=False,
            task_archiver=tar,
        )
        ts._verify_header_sig = lambda x: True
        self.ts = ts
        ts._is_address_accessible = Mock(return_value=True)
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        ts.client.get_requesting_trust.return_value = 0.3
        self.assertIsInstance(ts, TaskServer)
        ts._request_random_task()

        keys_auth = KeysAuth(self.path, 'prv_key', '')
        task_header = get_example_task_header(keys_auth.public_key)
        task_id = task_header.task_id
        task_owner_key = task_header.task_owner.key  # pylint: disable=no-member

        self._prepare_handshake(task_owner_key, task_id)

        env_mock = Mock(spec=OldEnv)
        env_mock.get_performance = Mock(return_value=0.0)
        self.ts.get_environment_by_id = Mock(return_value=env_mock)
        self._prepare_keys_auth()
        ts.add_task_header(task_header)
        ts._request_random_task()
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
        ts._request_random_task()
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
        ts._request_random_task()
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
        ts._request_random_task()
        tar.add_support_status.assert_called_with(
            task_id5,
            SupportStatus(
                False,
                {UnsupportReason.DENY_LIST: keys_auth.key_id}))
        assert ts.remove_task_header(task_id5)

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
                node_id, "127.0.0.1", 'tid', 27.18, 1, 'oh')
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
        ts.client.get_computing_trust = Mock(return_value=1.0)

        self._prepare_env()

        ids = f'provider={node_name_id}, task_id={task_id}'

        with self.assertLogs(logger, level='INFO') as cm:
            # when
            accepted = ts.should_accept_provider(
                node_id, "127.0.0.1", task_id, provider_perf,
                DEFAULT_MAX_MEMORY_SIZE_KB, 'oh')

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
                DEFAULT_MAX_MEMORY_SIZE_KB, 'oh')

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
            DEFAULT_MAX_MEMORY_SIZE_KB, 'oh')

        # given
        self.client.get_computing_trust.return_value = \
            ts.config_desc.computing_trust
        # when/then
        assert ts.should_accept_provider(
            node_id, "127.0.0.1", task_id, DEFAULT_PROVIDER_PERF,
            DEFAULT_MAX_MEMORY_SIZE_KB, 'oh')

        # given
        trust = ts.config_desc.computing_trust - 0.2
        self.client.get_computing_trust.return_value = trust
        with self.assertLogs(logger, level='INFO') as cm:
            # when
            accepted = ts.should_accept_provider(
                node_id, "127.0.0.1", task_id, DEFAULT_PROVIDER_PERF,
                DEFAULT_MAX_MEMORY_SIZE_KB, 'oh')

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
                DEFAULT_MAX_MEMORY_SIZE_KB, 'oh')

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
                                                 task_id, 99, 4, 'oh')

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
        ts.disallow_node(node_id)
        # then
        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(
                node_id=node_id,
                ip_addr="127.0.0.1",
                task_id=task_id,
                provider_perf=DEFAULT_PROVIDER_PERF,
                max_memory_size=DEFAULT_MAX_MEMORY_SIZE_KB,
                offer_hash='oh'
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
        ts.disallow_ip("127.0.0.1")
        # then
        assert not ts.should_accept_provider(
            "XYZ", "127.0.0.1", task_id, DEFAULT_PROVIDER_PERF,
            DEFAULT_MAX_MEMORY_SIZE_KB, 'oh')
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

        ts.disallow_node("ABC")
        ss = ts.should_accept_requestor("ABC")
        assert not ss.is_ok()
        assert UnsupportReason.DENY_LIST in ss.desc
        self.assertEqual(ss.desc[UnsupportReason.DENY_LIST], "ABC")

    def test_disallow_node(self, *_):
        # given
        ts = self.ts
        ts.acl = Mock()

        # when
        ts.disallow_node('ABC', 314, True)

        # then
        ts.acl.disallow.assert_called_once_with('ABC', 314, True)

    def test_disallow_ip(self, *_):
        # given
        ts = self.ts
        ts.acl_ip = Mock()

        # when
        ts.disallow_ip('ABC', 314)

        # then
        ts.acl_ip.disallow.assert_called_once_with('ABC', 314)

    def test_allow_node(self, *_):
        # given
        ts = self.ts
        ts.acl = Mock()

        # when
        ts.allow_node('ABC')

        # then
        ts.acl.allow.assert_called_once_with('ABC', True)

    def test_allow_node_not_persistent(self, *_):
        # given
        ts = self.ts
        ts.acl = Mock()

        # when
        ts.allow_node('ABC', False)

        # then
        ts.acl.allow.assert_called_once_with('ABC', False)

    def test_allow_ip(self, *_):
        # given
        ts = self.ts
        ts.acl_ip = Mock()

        # when
        ts.allow_ip('ABC', 314)

        # then
        ts.acl_ip.allow.assert_called_once_with('ABC', 314)

    def test_acl_status(self, *_):
        # given
        ts = self.ts
        ts.acl = Mock()
        status_mock = Mock()
        ts.acl.status.return_value = status_mock

        # when
        ts.acl_status()

        # then
        ts.acl.status.assert_called_once_with()
        status_mock.to_message.assert_called_once_with()

    def test_default_acl_status(self, *_):
        # when
        acl_status = self.ts.acl_status()

        # then
        assert acl_status['default_rule'] == 'allow'
        assert not acl_status['rules']

    def test_acl_ip_status(self, *_):
        # given
        ts = self.ts
        ts.acl_ip = Mock()
        status_mock = Mock()
        ts.acl_ip.status.return_value = status_mock

        # when
        ts.acl_ip_status()

        # then
        ts.acl_ip.status.assert_called_once_with()
        status_mock.to_message.assert_called_once_with()

    def test_acl_setup_default_deny(self, *_):
        # given
        ts = self.ts

        # when
        ts.acl_setup('deny', [])

        # then
        assert ts.acl.status().default_rule == AclRule.deny
        assert not ts.acl.status().rules

    def test_acl_setup_default_allow(self, *_):
        # given
        ts = self.ts

        # when
        ts.acl_setup('allow', [])

        # then
        assert ts.acl.status().default_rule == AclRule.allow
        assert not ts.acl.status().rules

    def test_acl_setup_default_inexistent(self, *_):
        # then
        with self.assertRaises(KeyError, None, 'not existent rule'):
            self.ts.acl_setup('not existent rule', [])

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
        assert not client_options.peers

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
        self.ts.resource_manager.build_client_options.return_value = \
            built_options

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

    def test_add_task_header_invalid_sig(self):
        self.ts._verify_header_sig = lambda _: False
        result = self.ts.add_task_header(Mock())
        self.assertFalse(result)


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
            "DEF", task_id, 1000, 10, 'oh')
        assert subtask is not None
        expected_value = ceil(1031 * 1010 / 3600)
        prev_calls = trust.COMPUTED.increase.call_count
        ts.accept_result("xxyyzz", "key", "eth_address", expected_value)
        ts.client.transaction_system.add_payment_info.assert_called_with(
            subtask_id="xxyyzz",
            value=expected_value,
            eth_address="eth_address",
            node_id=task_mock.header.task_owner.key,  # noqa pylint: disable=no-member
            task_id=task_mock.header.task_id,
        )
        self.assertGreater(trust.COMPUTED.increase.call_count, prev_calls)

    def test_disconnect(self, *_):
        session_mock = Mock()
        self.ts.sessions['active_node_id'] = session_mock
        self.ts.sessions['pending_node_id'] = None
        self.ts.disconnect()
        session_mock.dropped.assert_called_once_with()


class TestSubtask(TaskServerBase):

    def test_waiting_requested_tasks(self, *_):
        task_id = str(uuid.uuid4())
        subtask_id = str(uuid.uuid4())
        self.ts.requested_tasks.add(task_id)
        self.ts.subtask_waiting(task_id, subtask_id)
        self.assertNotIn(task_id, self.ts.requested_tasks)

    @patch('golem.task.taskserver.Trust.PAYMENT.decrease')
    def test_subtask_rejected(self, mock_decrease):
        mock_send = self.ts._task_result_sent = Mock()
        node_id = str(uuid.uuid4())
        subtask_id = str(uuid.uuid4())
        self.ts.subtask_rejected(node_id, subtask_id)
        mock_send.assert_called_once_with(subtask_id)
        mock_decrease.assert_called_once_with(node_id, self.ts.max_trust)

    @patch('golem.task.taskserver.Trust.PAYMENT.increase')
    @patch('golem.task.taskserver.update_requestor_paid_sum')
    def test_income_listener_confirmed(self, mock_increase, mock_update):
        node_id = str(uuid.uuid4())
        amt = 1
        self.ts.income_listener(event="confirmed", node_id=node_id, amount=amt)
        mock_increase.assert_called_once_with(node_id, self.ts.max_trust)
        mock_update.assert_called_once_with(node_id, amt)

    @patch('golem.task.taskserver.Trust.PAYMENT.decrease')
    def test_income_listener_overdue(self, mock_decrease):
        node_id = str(uuid.uuid4())
        self.ts.income_listener(event="overdue_single", node_id=node_id)
        mock_decrease.assert_called_once_with(node_id, self.ts.max_trust)


class TestRestoreResources(LogTestCase, testutils.DatabaseFixture,
                           testutils.TestWithClient):

    @patch('golem.task.taskserver.NonHypervisedDockerCPUEnvironment')
    def setUp(self, docker_env):  # pylint: disable=arguments-differ
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
        docker_env().metadata.return_value.id = DockerCPUEnvironment.ENV_ID
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

    def test_no_results(self):
        with self.assertRaises(ValueError):
            self.ts.send_results('subtask_id', 'task_id', [])

    def test_subtask_already_sent(self):
        self.ts.results_to_send['subtask_id'] = Mock(spec=WaitingTaskResult)
        with self.assertRaises(RuntimeError):
            self.ts.send_results('subtask_id', 'task_id', ['data'])

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
            self.ts.send_results('subtask_id', 'task_id', ['data'])

        result = self.ts.results_to_send.get('subtask_id')
        self.assertIsInstance(result, WaitingTaskResult)
        self.assertEqual(result.task_id, 'task_id')
        self.assertEqual(result.subtask_id, 'subtask_id')
        self.assertEqual(result.result, ['data'])
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

    def test_task_api(self):
        subtask_id = 'test_subtask_id'
        task_id = 'test_task_id'
        filepath = 'test_filepath'
        self.ts.task_keeper.task_headers[task_id] = Mock()
        self.ts.new_resource_manager = \
            Mock(spec=resourcemanager.ResourceManager)

        self.ts.send_results(subtask_id, task_id, task_api_result=filepath)

        self.ts.new_resource_manager.share.assert_called_once_with(filepath)
        wtr = self.ts.results_to_send[subtask_id]
        self.assertEqual(
            self.ts.new_resource_manager.share.return_value,
            wtr.result_hash,
        )
        self.assertEqual(filepath, wtr.result)


@patch('golem.task.taskserver.TaskServer.request_resource')
@patch('golem.task.taskserver.update_requestor_assigned_sum')
@patch('golem.task.taskserver.dispatcher')
@patch('golem.task.taskserver.logger')
class TestTaskGiven(TaskServerTestBase):
    # pylint: disable=too-many-arguments

    def test_ok(
            self, logger_mock, dispatcher_mock, update_requestor_assigned_sum,
            request_resource):

        self.ts.task_computer.has_assigned_task.return_value = False
        ttc = msg_factories.tasks.TaskToComputeFactory()

        result = self.ts.task_given(ttc)
        self.assertEqual(result, True)

        self.ts.task_computer.task_given.assert_called_once_with(
            ttc.compute_task_def
        )
        request_resource.assert_called_once_with(
            ttc.task_id,
            ttc.subtask_id,
            ttc.compute_task_def['resources'],  # noqa pylint: disable=unsubscriptable-object
            ttc.resources_options,
        )
        update_requestor_assigned_sum.assert_called_once_with(
            ttc.requestor_id,
            ttc.price,
        )
        dispatcher_mock.send.assert_called_once_with(
            signal='golem.subtask',
            event='started',
            subtask_id=ttc.subtask_id,
            price=ttc.price,
        )
        logger_mock.error.assert_not_called()

    def test_already_assigned(
            self, logger_mock, dispatcher_mock, update_requestor_assigned_sum,
            request_resource):

        self.ts.task_computer.has_assigned_task.return_value = True
        result = self.ts.task_given(Mock())
        self.assertEqual(result, False)

        self.ts.task_computer.task_given.assert_not_called()
        request_resource.assert_not_called()
        update_requestor_assigned_sum.assert_not_called()
        dispatcher_mock.send.assert_not_called()
        logger_mock.error.assert_called()

    def test_task_api(
            self, _logger_mock, _dispatcher_mock,
            _update_requestor_assigned_sum, _request_resource):
        self.ts.task_computer.has_assigned_task.return_value = False
        ttc = msg_factories.tasks.TaskToComputeFactory()
        ttc.want_to_compute_task.task_header.environment_prerequisites = Mock()
        self.assertTrue(ttc.compute_task_def['resources'])  # noqa pylint: disable=unsubscriptable-object
        self.ts.new_resource_manager = \
            Mock(spec=resourcemanager.ResourceManager)
        self.ts.task_computer._new_computer = Mock()

        self.ts.task_given(ttc)

        for resource in ttc.compute_task_def['resources']:  # noqa pylint: disable=unsubscriptable-object
            self.ts.new_resource_manager.download.assert_any_call(
                resource,
                self.ts.task_computer.get_subtask_inputs_dir.return_value,
                ttc.resources_options,
            )
        self.assertEqual(
            len(ttc.compute_task_def['resources']),  # noqa pylint: disable=unsubscriptable-object
            self.ts.new_resource_manager.download.call_count,
        )


@patch('golem.task.taskserver.logger')
class TestResourceCollected(TaskServerTestBase):

    def test_wrong_task_id(self, logger_mock):
        self.ts.task_computer.assigned_task_id = 'test'
        result = self.ts.resource_collected('wrong_id')
        self.assertFalse(result)
        logger_mock.error.assert_called_once()
        self.ts.task_computer.start_computation.assert_not_called()

    def test_ok(self, logger_mock):
        self.ts.task_computer.assigned_task_id = 'test'
        result = self.ts.resource_collected('test')
        self.assertTrue(result)
        logger_mock.error.assert_not_called()
        self.ts.task_computer.start_computation.assert_called_once_with()


@patch('golem.task.taskserver.logger')
@patch('golem.task.taskserver.TaskServer.send_task_failed')
class TestResourceFailure(TaskServerTestBase):

    def test_wrong_task_id(self, send_task_failed, logger_mock):
        self.ts.task_computer.assigned_task_id = 'test'
        self.ts.resource_failure('wrong_id', 'reason')
        logger_mock.error.assert_called_once()
        self.ts.task_computer.task_interrupted.assert_not_called()
        send_task_failed.assert_not_called()

    def test_ok(self, send_task_failed, logger_mock):
        self.ts.task_computer.assigned_task_id = 'test_task'
        self.ts.task_computer.assigned_subtask_id = 'test_subtask'
        self.ts.resource_failure('test_task', 'test_reason')
        logger_mock.error.assert_not_called()
        self.ts.task_computer.task_interrupted.assert_called_once_with()
        send_task_failed.assert_called_once_with(
            'test_subtask',
            'test_task',
            'Error downloading resources: test_reason'
        )


class TestRequestRandomTask(TaskServerTestBase):

    def setUp(self):
        super().setUp()
        self.ts.task_keeper = MagicMock()

    @freezegun.freeze_time()
    def test_request_interval(self):
        self.ts.config_desc.task_request_interval = 1.0
        self.ts._last_task_request_time = time.time()
        with patch.object(self.ts, '_request_task') as mock_req:
            self.ts._request_random_task()
            mock_req.assert_not_called()

    @freezegun.freeze_time()
    def test_task_already_assigned(self):
        self.ts.config_desc.task_request_interval = 1.0
        self.ts._last_task_request_time = time.time() - 1.0
        self.ts.task_computer.has_assigned_task.return_value = True
        self.ts.task_computer.compute_tasks = True
        self.ts.task_computer.runnable = True

        with patch.object(self.ts, '_request_task') as mock_req:
            self.ts._request_random_task()
            mock_req.assert_not_called()

    @freezegun.freeze_time()
    def test_task_computer_not_accepting_tasks(self):
        self.ts.config_desc.task_request_interval = 1.0
        self.ts._last_task_request_time = time.time() - 1.0
        self.ts.task_computer.has_assigned_task.return_value = False
        self.ts.task_computer.compute_tasks = False
        self.ts.task_computer.runnable = True

        with patch.object(self.ts, '_request_task') as mock_req:
            self.ts._request_random_task()
            mock_req.assert_not_called()

    @freezegun.freeze_time()
    def test_task_computer_not_runnable(self):
        self.ts.config_desc.task_request_interval = 1.0
        self.ts._last_task_request_time = time.time() - 1.0
        self.ts.task_computer.has_assigned_task.return_value = False
        self.ts.task_computer.compute_tasks = True
        self.ts.task_computer.runnable = False

        with patch.object(self.ts, '_request_task') as mock_req:
            self.ts._request_random_task()
            mock_req.assert_not_called()

    @freezegun.freeze_time()
    def test_no_supported_tasks_in_task_keeper(self):
        self.ts.config_desc.task_request_interval = 1.0
        self.ts._last_task_request_time = time.time() - 1.0
        self.ts.task_computer.has_assigned_task.return_value = False
        self.ts.task_computer.compute_tasks = True
        self.ts.task_computer.runnable = True
        self.ts.task_keeper.get_task.return_value = None

        with patch.object(self.ts, '_request_task') as mock_req:
            self.ts._request_random_task()
            mock_req.assert_not_called()

    @freezegun.freeze_time()
    @patch('golem.task.taskserver.TaskServer._request_task')
    def test_ok(self, request_task):
        self.ts.config_desc.task_request_interval = 1.0
        self.ts._last_task_request_time = time.time() - 1.0
        self.ts.task_computer.has_assigned_task.return_value = False
        self.ts.task_computer.compute_tasks = True
        self.ts.task_computer.runnable = True
        task_header = Mock()
        self.ts.task_keeper.get_task.return_value = task_header

        self.ts._request_random_task()
        self.assertEqual(self.ts._last_task_request_time, time.time())
        self.ts.task_computer.stats.increase_stat.assert_called_once_with(
            'tasks_requested')
        request_task.assert_called_once_with(task_header)


class TaskServerAsyncTestBase(TaskServerTestBase, TwistedTestCase):

    def _patch_async(self, *args, **kwargs):
        patcher = patch(*args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _patch_ts_async(self, *args, **kwargs):
        patcher = patch.object(self.ts, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()


class TestChangeConfig(TaskServerAsyncTestBase):

    @defer.inlineCallbacks
    def test(self):
        change_tc_config = self._patch_ts_async('_change_task_computer_config')
        change_tk_config = self._patch_ts_async('task_keeper').change_config
        change_pcs_config = \
            self._patch_async('golem.task.taskserver.PendingConnectionsServer')\
                .change_config

        change_tc_config.return_value = defer.succeed(None)
        change_tk_config.return_value = defer.succeed(None)
        config_desc = ClientConfigDescriptor()

        yield self.ts.change_config(config_desc, run_benchmarks=True)
        change_tc_config.assert_called_once_with(config_desc, True)
        change_tk_config.assert_called_once_with(config_desc)
        change_pcs_config.assert_called_once_with(self.ts, config_desc)


class ChangeTaskComputerConfig(TaskServerAsyncTestBase):

    @defer.inlineCallbacks
    def test_config_unchanged_no_benchmarks(self):
        change_tc_config = self._patch_ts_async('task_computer').change_config
        change_tc_config.return_value = defer.succeed(False)
        run_benchmarks = self._patch_ts_async('benchmark_manager')\
            .run_all_benchmarks
        config_desc = ClientConfigDescriptor()

        yield self.ts._change_task_computer_config(config_desc, False)
        change_tc_config.assert_called_once_with(config_desc)
        run_benchmarks.assert_not_called()

    @defer.inlineCallbacks
    def test_config_changed_no_benchmarks(self):
        task_computer = self._patch_ts_async('task_computer')
        task_computer.change_config.return_value = defer.succeed(True)
        run_benchmarks = self._patch_ts_async('benchmark_manager')\
            .run_all_benchmarks

        def _check(callback, _):
            task_computer.lock_config.assert_called_once_with(True)
            task_computer.lock_config.reset_mock()
            callback(None)

        run_benchmarks.side_effect = _check
        config_desc = ClientConfigDescriptor()

        yield self.ts._change_task_computer_config(config_desc, False)
        task_computer.change_config.assert_called_once_with(config_desc)
        task_computer.lock_config.assert_called_once_with(False)
        run_benchmarks.assert_called_once()

    @defer.inlineCallbacks
    def test_config_unchanged_run_benchmarks(self):
        task_computer = self._patch_ts_async('task_computer')
        task_computer.change_config.return_value = defer.succeed(False)
        run_benchmarks = self._patch_ts_async('benchmark_manager')\
            .run_all_benchmarks

        def _check(callback, _):
            task_computer.lock_config.assert_called_once_with(True)
            task_computer.lock_config.reset_mock()
            callback(None)

        run_benchmarks.side_effect = _check
        config_desc = ClientConfigDescriptor()

        yield self.ts._change_task_computer_config(config_desc, True)
        task_computer.change_config.assert_called_once_with(config_desc)
        task_computer.lock_config.assert_called_once_with(False)
        run_benchmarks.assert_called_once()


class TestTaskServerConcent(TaskServerAsyncTestBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp()
        self._patch_ts_async(
            'should_accept_requestor',
            return_value=SupportStatus(True)
        )

    @defer.inlineCallbacks
    def test_request_task_concent_required(self):
        self.ts.client.concent_service.enabled = True
        self.ts.client.concent_service.required_as_provider = True
        task_header = get_example_task_header('test')
        task_header.max_price = self.ccd.max_price
        task_header.concent_enabled = False

        result = yield self.ts._request_task(task_header)

        self.assertIsNone(result)
        self.ts.task_archiver.add_support_status.assert_called_once_with(
            task_header.task_id,
            SupportStatus(
                False,
                {UnsupportReason.CONCENT_REQUIRED: True},
            ),
        )

    @defer.inlineCallbacks
    def test_request_task_concent_enabled_but_not_required(self, *_):
        self.ts.client.concent_service.enabled = True
        self.ts.client.concent_service.required_as_provider = False

        env = Mock(spec=OldEnv)
        env.get_performance.return_value = 0
        self._patch_ts_async('get_environment_by_id', return_value=env)

        task_header = get_example_task_header('test')
        task_header.max_price = self.ccd.max_price
        task_header.concent_enabled = False

        handshake = MagicMock()
        handshake.success.return_value = True
        self.ts.resource_handshakes[task_header.task_owner.key] = handshake  # noqa pylint: disable=no-member

        result = yield self.ts._request_task(task_header)

        self.assertEqual(result, task_header.task_id)
        self.assertIn(
            task_header.task_id,
            self.ts.requested_tasks
        )


class TestEnvManager(TaskServerAsyncTestBase):
    def test_get_environment_by_id(self):
        # Given
        env_manager = self.ts.task_keeper.new_env_manager
        env_manager.enabled = Mock(return_value=True)
        env_manager.environment = Mock()
        env_id = "env1"

        # When
        self.ts.get_environment_by_id(env_id)

        # Then
        env_manager.enabled.assert_called_with(env_id)
        env_manager.environment.assert_called_with(env_id)

    def test_get_environment_by_id_not_found(self):
        # Given
        env_manager = self.ts.task_keeper.new_env_manager
        env_manager.enabled = Mock(return_value=False)
        env_manager.environment = Mock()
        env_id = "env1"

        # When
        self.ts.get_environment_by_id(env_id)

        # Then
        env_manager.enabled.assert_called_with(env_id)
        env_manager.environment.assert_not_called()

    @defer.inlineCallbacks
    def test_request_task(self):
        # Given

        task_header = get_example_task_header('abc')

        self.ts.should_accept_requestor = Mock(return_value=SupportStatus.ok())
        self.ts.client.concent_service.enabled = False
        self.ts.config_desc.min_price = task_header.max_price

        mock_env = Mock(spec=NewEnv)
        self.ts.get_environment_by_id = Mock(return_value=mock_env)

        mock_get = Mock(return_value=300.0)
        self.ts.task_keeper.new_env_manager.get_performance = mock_get

        mock_handshake = Mock()
        mock_handshake.success = Mock(return_value=True)
        self.ts.resource_handshakes[
            task_header.task_owner.key  # pylint: disable=no-member
        ] = mock_handshake

        # When
        yield self.ts._request_task(task_header)

        # Then
        mock_get.assert_called_once()

    @defer.inlineCallbacks
    def test_request_task_running_benchmark(self):
        # Given
        performance = None
        task_header = get_example_task_header('abc')

        self.ts.should_accept_requestor = Mock(return_value=SupportStatus.ok())
        self.ts.client.concent_service.enabled = False
        self.ts.config_desc.min_price = task_header.max_price

        mock_env = Mock(spec=NewEnv)
        self.ts.get_environment_by_id = Mock(return_value=mock_env)

        mock_get = Mock(return_value=performance)
        self.ts.task_keeper.new_env_manager.get_performance = mock_get

        mock_handshake = Mock()
        mock_handshake.success = Mock(return_value=True)
        self.ts.resource_handshakes[
            task_header.task_owner.key  # pylint: disable=no-member
        ] = mock_handshake

        # When
        result = yield self.ts._request_task(task_header)

        self.assertEqual(result, performance)
        mock_get.assert_called_once()

    def test_get_min_performance_for_task(self):
        # Given
        mock_env = Mock(spec=NewEnv)
        self.ts.get_environment_by_id = Mock(return_value=mock_env)
        task = get_mock_task()

        # When
        result = self.ts.get_min_performance_for_task(task)

        # Then
        self.ts.get_environment_by_id.assert_called_once()
        self.assertEqual(result, 0.0)


class TestNewTaskComputerIntegration(
        testutils.TestWithClient,
        testutils.DatabaseFixture,
        TwistedTestCase
):

    @classmethod
    def setUpClass(cls):
        try:
            uninstall_reactor()  # Because other tests don't clean up
        except AttributeError:
            pass
        asyncio.set_event_loop(asyncio.new_event_loop())
        install_reactor()

    @classmethod
    def cleanUpClass(cls):
        uninstall_reactor()

    @patch('golem.task.taskserver.TaskHeaderKeeper', spec=TaskHeaderKeeper)
    @patch('golem.task.taskserver.ResourceManager', spec_set=ResourceManager)
    @patch('golem.task.taskserver.BenchmarkManager', spec_set=BenchmarkManager)
    @patch('golem.task.taskserver.TaskManager', spec=TaskManager)
    @patch('golem.task.taskserver.NonHypervisedDockerCPUEnvironment')
    @patch(
        'golem.task.taskserver.DockerTaskApiPayloadBuilder',
        LocalhostPayloadBuilder
    )
    def setUp(  # pylint: disable=too-many-arguments,arguments-differ
            self,
            docker_env,
            task_manager,
            benchmark_manager,
            resource_manager,
            task_header_keeper,
    ):
        testutils.TestWithClient.setUp(self)
        testutils.DatabaseFixture.setUp(self)

        docker_env.return_value = LocalhostEnvironment(
            config=LocalhostConfig(),
            env_id=DockerCPUEnvironment.ENV_ID
        )
        benchmark_manager().benchmarks_needed.return_value = False
        self.resource_manager = resource_manager()
        self.resource_manager.download.return_value = defer.succeed(None)
        self.task_header_keeper = task_header_keeper()
        self.comp_task_keeper = Mock(spec=CompTaskKeeper)
        task_manager.return_value.apps_manager = Mock()
        task_manager.return_value.comp_task_keeper = self.comp_task_keeper

        trust_patch = patch('golem.task.taskserver.Trust')
        self.addCleanup(trust_patch.stop)
        self.trust = trust_patch.start()

        self.task_finished = defer.Deferred()
        self.task_server = TaskServer(
            node=dt_p2p_factory.Node(),
            config_desc=ClientConfigDescriptor(),
            client=self.client,
            task_finished_cb=lambda: self.task_finished.callback(None),
            use_docker_manager=False
        )

    @property
    def task_id(self):
        return 'test_task'

    @property
    def subtask_id(self):
        return 'test_subtask'

    @property
    def subtask_params(self):
        return {'param': 'value'}

    @property
    def env_id(self):
        return DockerCPUEnvironment.ENV_ID

    def _get_task_to_compute(self, prereq):
        msg = msg_factories.tasks.TaskToComputeFactory()
        # pylint: disable=unsupported-assignment-operation
        msg.compute_task_def['task_id'] = self.task_id
        msg.compute_task_def['subtask_id'] = self.subtask_id
        msg.compute_task_def['resources'] = ['test_resource']
        msg.compute_task_def['extra_data'] = self.subtask_params
        # pylint: enable=unsupported-assignment-operation
        task_header = msg.want_to_compute_task.task_header
        task_header.task_id = self.task_id
        task_header.environment = self.env_id
        task_header.environment_prerequisites = prereq.to_dict()
        comp_task_info = CompTaskInfo(task_header, 1.2)

        self.task_header_keeper.task_headers = {self.task_id: task_header}
        self.comp_task_keeper.get_task_id_for_subtask.return_value = \
            self.task_id
        self.comp_task_keeper.get_task_header.return_value = task_header
        self.comp_task_keeper.get_node_for_task_id.return_value = 'test_node'
        self.comp_task_keeper.active_tasks = {self.task_id: comp_task_info}

        return msg

    @defer.inlineCallbacks
    def test_successful_computation(self):
        # Given
        result_path = 'test_result'
        result_hash = 'test_result_hash'
        self.resource_manager.share.return_value = result_hash

        subtask_id = self.subtask_id
        subtask_params = self.subtask_params

        async def compute(given_id, given_params):
            assert given_id == subtask_id
            assert given_params == subtask_params
            return result_path

        prereq = LocalhostPrerequisites(compute=compute)
        msg = self._get_task_to_compute(prereq)

        # When
        self.task_server.task_given(msg)
        yield self.task_finished  # Wait for the task to finish

        # Then
        task_computer_root = Path(self.task_server.get_task_computer_root())
        full_result_path = \
            task_computer_root / self.env_id / self.task_id / result_path
        self.resource_manager.share.asssert_called_once_with(full_result_path)

        result_to_send = self.task_server.results_to_send[self.subtask_id]
        self.assertEqual(result_to_send.task_id, self.task_id)
        self.assertEqual(result_to_send.subtask_id, self.subtask_id)
        self.assertEqual(result_to_send.result, full_result_path)
        self.assertEqual(result_to_send.result_hash, result_hash)
        self.assertNotIn(self.subtask_id, self.task_server.failures_to_send)

        self.trust.REQUESTED.increase.assert_called_once_with(
            msg.want_to_compute_task.task_header.task_owner.key)
        self.trust.REQUESTED.decrease.assert_not_called()

        self.assertEqual(
            self.task_header_keeper.method_calls, [
                call.task_started(self.task_id),
                call.task_ended(self.task_id)
            ]
        )

    @defer.inlineCallbacks
    def test_computation_error(self):
        # Given
        error_msg = 'computation failed'

        async def compute(_, __):
            raise OSError(error_msg)

        prereq = LocalhostPrerequisites(compute=compute)
        msg = self._get_task_to_compute(prereq)

        # When
        self.task_server.task_given(msg)
        yield self.task_finished  # Wait for the task to finish

        # Then
        self.resource_manager.share.asssert_not_called()

        self.assertNotIn(self.subtask_id, self.task_server.results_to_send)
        failure_to_send = self.task_server.failures_to_send[self.subtask_id]
        self.assertEqual(failure_to_send.task_id, self.task_id)
        self.assertEqual(failure_to_send.subtask_id, self.subtask_id)
        self.assertEqual(
            failure_to_send.owner,
            msg.want_to_compute_task.task_header.task_owner)
        self.assertIn(error_msg, failure_to_send.err_msg)

        self.trust.REQUESTED.increase.assert_not_called()
        self.trust.REQUESTED.decrease.assert_called_once_with(
            msg.want_to_compute_task.task_header.task_owner.key)

        self.assertEqual(
            self.task_header_keeper.method_calls, [
                call.task_started(self.task_id),
                call.task_ended(self.task_id)
            ]
        )

    @defer.inlineCallbacks
    def test_computation_timed_out(self):
        # Given
        async def compute(_, __):
            await asyncio.sleep(10)
            return ''

        prereq = LocalhostPrerequisites(compute=compute)
        msg = self._get_task_to_compute(prereq)
        msg.want_to_compute_task.task_header.deadline = time.time()

        # When
        self.task_server.task_given(msg)
        yield self.task_finished  # Wait for the task to finish

        # Then
        self.resource_manager.share.asssert_not_called()

        self.assertNotIn(self.subtask_id, self.task_server.results_to_send)
        self.assertNotIn(self.subtask_id, self.task_server.failures_to_send)

        self.trust.REQUESTED.increase.assert_not_called()
        self.trust.REQUESTED.decrease.assert_not_called()

        self.assertEqual(
            self.task_header_keeper.method_calls, [
                call.task_started(self.task_id),
                call.task_ended(self.task_id)
            ]
        )
