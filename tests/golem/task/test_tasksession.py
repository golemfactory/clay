import os
import pathlib
import pickle
import random
import unittest
import uuid
from unittest.mock import Mock, MagicMock, patch

from golem_messages import message

from apps.core.task.coretask import TaskResourceHeader
from golem import model
from golem import testutils
from golem.core.databuffer import DataBuffer
from golem.core.keysauth import KeysAuth, EllipticalKeysAuth
from golem.core.variables import PROTOCOL_CONST
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.model import Actor
from golem.network.p2p.node import Node
from golem.network.transport.tcpnetwork import BasicProtocol
from golem.resource.client import ClientOptions
from golem.task.taskbase import ResultType
from golem.task.taskkeeper import CompTaskKeeper
from golem.task.taskserver import WaitingTaskResult
from golem.task.tasksession import TaskSession, logger
from golem.tools.assertlogs import LogTestCase


class DockerEnvironmentMock(DockerEnvironment):
    DOCKER_IMAGE = ""
    DOCKER_TAG = ""
    ENV_ID = ""
    APP_DIR = ""
    SCRIPT_NAME = ""
    SHORT_DESCRIPTION = ""


class TestTaskSession(LogTestCase, testutils.TempDirFixture,
                      testutils.PEP8MixIn):
    PEP8_FILES = ['golem/task/tasksession.py', ]

    def setUp(self):
        super(TestTaskSession, self).setUp()
        random.seed()
        self.task_session = TaskSession(Mock())

    @patch('golem.task.tasksession.TaskSession.send')
    def test_hello(self, send_mock):
        self.task_session.conn.server.get_key_id.return_value = key_id = 'key id%d' % (random.random() * 1000,)
        self.task_session.send_hello()
        expected = [
            ['rand_val', self.task_session.rand_val],
            ['proto_id', PROTOCOL_CONST.TASK_ID],
            ['node_name', None],
            ['node_info', None],
            ['port', 0],
            ['client_ver', 0],
            ['client_key_id', key_id],
            ['solve_challenge', False],
            ['challenge', None],
            ['difficulty', 0],
            ['metadata', None],
        ]
        msg = send_mock.call_args[0][0]
        self.assertEqual(msg.slots(), expected)

    def test_encrypt(self):
        ts = TaskSession(Mock())
        data = "ABC"

        ts.key_id = "123"
        ts.encrypt(data)
        ts.task_server.encrypt.assert_called_with(data, "123")

        ts.task_server = None
        with self.assertLogs(logger, level='WARNING'):
            self.assertEqual(ts.encrypt(data), data)

    def test_decrypt(self):
        ts = TaskSession(Mock())
        data = "ABC"

        res = ts.decrypt(data)
        ts.task_server.decrypt.assert_called_with(data)
        self.assertIsNotNone(res)

        ts.task_server.decrypt = Mock(side_effect=AssertionError("Encrypt error"))
        with self.assertLogs(logger, level='INFO') as l:
            res = ts.decrypt(data)
        self.assertTrue(any("maybe it's not encrypted?" in log for log in l.output))
        self.assertFalse(any("Encrypt error" in log for log in l.output))
        self.assertEqual(res, data)

        ts.task_server.decrypt = Mock(side_effect=ValueError("Different error"))
        with self.assertLogs(logger, level='DEBUG') as l:
            res = ts.decrypt(data)
        self.assertTrue(any("Different error" in log for log in l.output))
        self.assertIsNone(res)

        ts.task_server = None
        data = "ABC"
        with self.assertLogs(logger, level='WARNING'):
            self.assertEqual(ts.encrypt(data), data)

    def test_request_task(self):
        conn = Mock(server=Mock(deny_set=set()))
        ts = TaskSession(conn)
        ts._get_handshake = Mock(return_value={})
        ts.verified = True
        ts.request_task("ABC", "xyz", 1030, 30, 3, 1, 8)
        mt = ts.conn.send_message.call_args[0][0]
        self.assertIsInstance(mt, message.WantToComputeTask)
        self.assertEqual(mt.node_name, "ABC")
        self.assertEqual(mt.task_id, "xyz")
        self.assertEqual(mt.perf_index, 1030)
        self.assertEqual(mt.price, 30)
        self.assertEqual(mt.max_resource_size, 3)
        self.assertEqual(mt.max_memory_size, 1)
        self.assertEqual(mt.num_cores, 8)
        ts2 = TaskSession(conn)
        ts2.verified = True
        ts2.key_id = "DEF"
        ts2.can_be_not_encrypted.append(mt.TYPE)
        ts2.can_be_unsigned.append(mt.TYPE)
        ts2.task_server.should_accept_provider.return_value = False
        ts2.task_server.config_desc.max_price = 100
        ts2.task_manager.get_next_subtask.return_value = ("CTD", False, False)
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, message.CannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)
        ts2.task_server.should_accept_provider.return_value = True
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, message.TaskToCompute)
        ts2.task_manager.get_next_subtask.return_value = ("CTD", True, False)
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, message.CannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)
        ts2.task_manager.get_node_id_for_subtask.return_value = "DEF"
        ts2._react_to_cannot_compute_task(message.CannotComputeTask(message.CannotComputeTask.REASON.WrongCTD))
        assert ts2.task_manager.task_computation_failure.called
        ts2.task_manager.task_computation_failure.called = False
        ts2.task_manager.get_node_id_for_subtask.return_value = "___"
        ts2._react_to_cannot_compute_task(message.CannotComputeTask(message.CannotComputeTask.REASON.WrongCTD))
        assert not ts2.task_manager.task_computation_failure.called

    def test_send_report_computed_task(self):
        ts = TaskSession(Mock())
        ts.sign = lambda x: b'\0' * message.Message.SIG_LEN
        ts.verified = True
        ts.task_server.get_node_name.return_value = "ABC"
        n = Node()
        wtr = WaitingTaskResult("xyz", "xxyyzz", "result", ResultType.DATA,
                                13190, 10, 0, "10.10.10.10",
                                30102, "key1", n)

        ts.send_report_computed_task(wtr, "10.10.10.10", 30102, "0x00", n)
        ms = ts.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, message.ReportComputedTask)
        self.assertEqual(ms.subtask_id, "xxyyzz")
        self.assertEqual(ms.result_type, ResultType.DATA)
        self.assertEqual(ms.computation_time, 13190)
        self.assertEqual(ms.node_name, "ABC")
        self.assertEqual(ms.address, "10.10.10.10")
        self.assertEqual(ms.port, 30102)
        self.assertEqual(ms.eth_account, "0x00")
        self.assertEqual(ms.extra_data, [])
        self.assertEqual(ms.node_info, n)
        ts2 = TaskSession(Mock())
        ts2.verified = True
        ts2.key_id = "DEF"
        ts2.can_be_not_encrypted.append(ms.TYPE)
        ts2.can_be_unsigned.append(ms.TYPE)
        ts2.task_manager.subtask2task_mapping = {"xxyyzz": "xyz"}
        ts2.interpret(ms)
        ts2.task_server.receive_subtask_computation_time.assert_called_with(
            "xxyyzz", 13190)
        wtr.result_type = "UNKNOWN"
        with self.assertLogs(logger, level="ERROR"):
            ts.send_report_computed_task(wtr, "10.10.10.10", 30102, "0x00", n)

    def test_react_to_hello(self):
        conn = MagicMock()

        node = Node(node_name='node', key='ffffffff')
        keys_auth = KeysAuth(self.path)
        keys_auth.key = node.key
        keys_auth.key_id = node.key

        ts = TaskSession(conn)
        ts.task_server = Mock()
        ts.disconnect = Mock()
        ts.send = Mock()

        def create_verify(value):
            def verify(*args):
                return value

            return verify

        key_id = 'deadbeef'
        peer_info = MagicMock()
        peer_info.key = key_id
        msg = message.Hello(port=1, node_name='node2', client_key_id=key_id, node_info=peer_info,
                           proto_id=-1)

        ts.verify = create_verify(False)
        ts._react_to_hello(msg)
        ts.disconnect.assert_called_with(
            message.Disconnect.REASON.Unverified)

        ts.verify = create_verify(True)
        ts._react_to_hello(msg)
        ts.disconnect.assert_called_with(
            message.Disconnect.REASON.ProtocolVersion)

        msg.proto_id = PROTOCOL_CONST.TASK_ID

        ts._react_to_hello(msg)
        assert ts.send.called

    def test_result_received(self):
        conn = Mock()
        ts = TaskSession(conn)
        ts.task_server = Mock()
        ts.task_manager = Mock()
        ts.task_manager.verify_subtask.return_value = True

        extra_data = dict(
            # the result is explicitly serialized using cPickle
            result=pickle.dumps({'stdout': 'xyz'}),
            result_type=None,
            subtask_id='xxyyzz'
        )

        ts.result_received(extra_data, decrypt=False)

        assert ts.msgs_to_send
        assert isinstance(ts.msgs_to_send[0], message.SubtaskResultRejected)
        assert conn.close.called

        extra_data.update(dict(
            result_type=ResultType.DATA,
        ))
        conn.close.called = False
        ts.msgs_to_send = []

        ts.result_received(extra_data, decrypt=False)

        assert ts.msgs_to_send
        assert ts.msgs_to_send[0].__class__ == message.SubtaskResultAccepted
        assert conn.close.called

        extra_data.update(dict(
            subtask_id=None,
        ))
        conn.close.called = False
        ts.msgs_to_send = []

        ts.result_received(extra_data, decrypt=False)

        assert not ts.msgs_to_send
        assert conn.close.called

    def test_react_to_task_result_hash(self):

        def create_pull_package(result):
            def pull_package(multihash, task_id, subtask_id,
                             secret, success, error, *args, **kwargs):
                if result:
                    success(Mock())
                else:
                    error(Exception('Pull failed'))

            return pull_package

        conn = Mock()
        ts = TaskSession(conn)
        ts.result_received = Mock()
        ts.task_manager.subtask2task_mapping = dict()

        subtask_id = 'xxyyzz'
        secret = 'pass'
        multihash = 'multihash'

        ts.task_manager.subtask2task_mapping[subtask_id] = 'xyz'

        msg = message.TaskResultHash(subtask_id=subtask_id, secret=secret, multihash=multihash,
                                    options=Mock())

        ts.task_manager.task_result_manager.pull_package = create_pull_package(True)
        ts._react_to_task_result_hash(msg)
        assert ts.result_received.called

        ts.task_manager.task_result_manager.pull_package = create_pull_package(False)
        ts._react_to_task_result_hash(msg)
        assert ts.task_server.reject_result.called
        assert ts.task_manager.task_computation_failure.called

        msg.subtask_id = "UNKNOWN"
        with self.assertLogs(logger, level="ERROR"):
            ts._react_to_task_result_hash(msg)

    def test_react_to_task_to_compute(self):
        conn = Mock()
        ts = TaskSession(conn)
        ts.key_id = "KEY_ID"
        ts.task_manager = Mock()
        ts.task_computer = Mock()
        ts.task_server = Mock()
        ts.send = Mock()

        env = Mock()
        env.docker_images = [DockerImage("dockerix/xii", tag="323")]
        env.allow_custom_main_program_file = False
        env.get_source_code.return_value = None
        ts.task_server.get_environment_by_id.return_value = env

        reasons = message.CannotComputeTask.REASON

        def __reset_mocks():
            ts.task_manager.reset_mock()
            ts.task_computer.reset_mock()
            conn.reset_mock()

        # msg.ctd is None -> failure
        msg = message.TaskToCompute(raw=b'\0')
        ts._react_to_task_to_compute(msg)
        ts.task_server.add_task_session.assert_not_called()
        ts.task_computer.task_given.assert_not_called()
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.send.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # No source code in the local environment -> failure
        __reset_mocks()
        ctd = message.ComputeTaskDef()
        ctd['key_id'] = "KEY_ID"
        ctd['subtask_id'] = "SUBTASKID"
        ctd['task_owner'] = Node()
        ctd['task_owner'].key = "KEY_ID"
        ctd['return_address'] = "10.10.10.10"
        ctd['return_port'] = 1112
        ctd['docker_images'] = [DockerImage("dockerix/xiii", tag="323")]
        msg = message.TaskToCompute(ctd, raw=b'\0')
        ts._react_to_task_to_compute(msg)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Source code from local environment -> proper execution
        __reset_mocks()
        env.get_source_code.return_value = "print 'Hello world'"
        ts._react_to_task_to_compute(msg)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_called_with(ctd)
        ts.task_computer.session_closed.assert_not_called()
        ts.task_server.add_task_session.assert_called_with("SUBTASKID", ts)
        ts.task_computer.task_given.assert_called_with(ctd)
        conn.close.assert_not_called()

        # Wrong key id -> failure
        __reset_mocks()
        ctd['key_id'] = "KEY_ID2"
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Wrong task owner key id -> failure
        __reset_mocks()
        ctd['key_id'] = "KEY_ID"
        ctd['task_owner'].key = "KEY_ID2"
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Wrong return port -> failure
        __reset_mocks()
        ctd['task_owner'].key = "KEY_ID"
        ctd['return_port'] = 0
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Proper port and key -> proper execution
        __reset_mocks()
        ctd['task_owner'].key = "KEY_ID"
        ctd['return_port'] = 1319
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        conn.close.assert_not_called()

        # Allow custom code / no code in message.ComputeTaskDef -> failure
        __reset_mocks()
        env.allow_custom_main_program_file = True
        ctd['src_code'] = ""
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Allow custom code / code in ComputerTaskDef -> proper execution
        __reset_mocks()
        ctd['src_code'] = "print 'Hello world!'"
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        ts.task_computer.session_closed.assert_not_called()
        ts.task_server.add_task_session.assert_called_with("SUBTASKID", ts)
        ts.task_computer.task_given.assert_called_with(ctd)
        conn.close.assert_not_called()

        # No environment available -> failure
        __reset_mocks()
        ts.task_server.get_environment_by_id.return_value = None
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        assert ts.err_msg == reasons.WrongEnvironment
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Envrionment is Docker environment but with different images -> failure
        __reset_mocks()
        ts.task_server.get_environment_by_id.return_value = \
            DockerEnvironmentMock(additional_images=[
                DockerImage("dockerix/xii", tag="323"),
                DockerImage("dockerix/xiii", tag="325"),
                DockerImage("dockerix/xiii")
            ])
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        assert ts.err_msg == reasons.WrongDockerImages
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Envrionment is Docker environment with proper images, but no srouce code -> failure
        __reset_mocks()
        de = DockerEnvironmentMock(additional_images=[
            DockerImage("dockerix/xii", tag="323"),
            DockerImage("dockerix/xiii", tag="325"),
            DockerImage("dockerix/xiii", tag="323")
        ])
        ts.task_server.get_environment_by_id.return_value = de
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        assert ts.err_msg == reasons.NoSourceCode
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        # Proper Docker environment with source code
        __reset_mocks()
        file_name = os.path.join(self.path, "main_program_file")
        with open(file_name, 'w') as f:
            f.write("Hello world!")
        de.main_program_file = file_name
        ts._react_to_task_to_compute(message.TaskToCompute(ctd, raw=b'\0'))
        ts.task_server.add_task_session.assert_called_with("SUBTASKID", ts)
        ts.task_computer.task_given.assert_called_with(ctd)
        conn.close.assert_not_called()

    def test_get_resource(self):
        conn = BasicProtocol()
        conn.transport = Mock()
        conn.server = Mock()

        db = DataBuffer()

        sess = TaskSession(conn)
        sess.send = lambda m: db.append_bytes(m.serialize(lambda x: b'\000'*65))
        sess._can_send = lambda *_: True
        sess.request_resource(str(uuid.uuid4()), TaskResourceHeader("tmp"))

        assert message.Message.deserialize(db.buffered_data, lambda x: x)

    def test_verify(self):
        keys_auth = EllipticalKeysAuth(self.path)
        conn = Mock()
        ts = TaskSession(conn)
        ts.task_server = Mock()
        ts.task_server.verify_sig = keys_auth.verify

        msg = message.RemoveTask()
        assert not ts.verify(msg)
        msg.sig = keys_auth.sign(msg.get_short_hash())
        ts.key_id = keys_auth.get_key_id()
        assert ts.verify(msg)

    def test_react_to_ack_reject_report_computed_task(self):
        task_keeper = CompTaskKeeper(pathlib.Path(self.path))

        session = self.task_session
        session.concent_service = MagicMock()
        session.task_manager.comp_task_keeper = task_keeper
        session.key_id = 'owner_id'

        msg_ack = message.AckReportComputedTask('subtask_id', raw=b'')
        msg_rej = message.RejectReportComputedTask('subtask_id', raw=b'')

        # Subtask is not known
        session._react_to_ack_report_computed_task(msg_ack)
        assert not session.concent_service.cancel.called
        session._react_to_reject_report_computed_task(msg_rej)
        assert not session.concent_service.cancel.called

        # Save subtask information
        task = Mock(header=Mock(task_owner_key_id='owner_id'))
        task_keeper.subtask_to_task['subtask_id'] = 'task_id'
        task_keeper.active_tasks['task_id'] = task

        # Subtask is known
        session._react_to_ack_report_computed_task(msg_ack)
        assert session.concent_service.cancel.called

        session.concent_service.cancel.reset_mock()
        session._react_to_reject_report_computed_task(msg_ack)
        assert session.concent_service.cancel.called

    @patch("golem.task.tasksession.TaskSession._check_msg", return_value=True)
    def test_react_to_subtask_payment(self, check_msg_mock):
        reward_mock = MagicMock()
        self.task_session.task_server.reward_for_subtask_paid = reward_mock
        subtask_id = str(uuid.uuid4())
        reward = random.randint(1, 2 ** 10)
        transaction_id = str(uuid.uuid4())
        block_number = random.randint(1, 2 ** 10)

        # Pending
        msg = message.SubtaskPayment(
            subtask_id=subtask_id,
            reward=reward,
            raw=b''
        )

        self.task_session.interpret(msg)
        reward_mock.assert_not_called()

        # Transaction created but not mined
        msg.transaction_id = transaction_id
        self.task_session.interpret(msg)
        reward_mock.assert_not_called()

        # Proper/finished transaction
        msg.block_number = block_number
        self.task_session.interpret(msg)

        reward_mock.assert_called_once_with(
            subtask_id=subtask_id,
            reward=reward,
            transaction_id=transaction_id,
            block_number=block_number
        )

    def test_react_to_resource_list(self):
        task_server = self.task_session.task_server

        client = 'test_client'
        version = 1.0
        peers = [{'TCP': ('127.0.0.1', 3282)}]
        client_options = ClientOptions(client, version,
                                       options={'peers': peers})
        msg = message.ResourceList(resources=[['1'], ['2']],
                                   options=client_options)

        # Use locally saved hyperdrive client options
        self.task_session._react_to_resource_list(msg)
        call_options = task_server.pull_resources.call_args[1]

        assert task_server.get_download_options.called
        assert task_server.pull_resources.called
        assert isinstance(call_options['client_options'], Mock)

        # Use remote options when local ones are not available
        task_server.get_download_options.return_value = ClientOptions(client,
                                                                      version)
        self.task_session.task_server.pull_resources.reset_mock()
        self.task_session._react_to_resource_list(msg)
        call_options = task_server.pull_resources.call_args[1]

        assert not isinstance(call_options['client_options'], Mock)
        assert call_options['client_options'].options['peers'] == peers

    def test_task_subtask_from_message(self):
        self.task_session._subtask_to_task = Mock(return_value=None)
        definition = message.ComputeTaskDef({'task_id': 't', 'subtask_id': 's'})
        msg = message.TaskToCompute(definition, raw=b'\0')

        task, subtask = self.task_session._task_subtask_from_message(
            msg, Actor.Provider)

        assert task == definition['task_id']
        assert subtask == definition['subtask_id']
        assert not self.task_session._subtask_to_task.called

    def test_task_subtask_from_other_message(self):
        self.task_session._subtask_to_task = Mock(return_value=None)
        msg = message.Hello(raw=b'\0')

        task, subtask = self.task_session._task_subtask_from_message(
            msg, Actor.Provider
        )

        assert not task
        assert not subtask
        assert self.task_session._subtask_to_task.called

    def test_subtask_to_task(self):
        task_keeper = Mock(subtask_to_task=dict())
        mapping = dict()

        self.task_session.task_manager.comp_task_keeper = task_keeper
        self.task_session.task_manager.subtask2task_mapping = mapping
        task_keeper.subtask_to_task['sid_1'] = 'task_1'
        mapping['sid_2'] = 'task_2'

        assert self.task_session._subtask_to_task('sid_1', Actor.Provider)
        assert self.task_session._subtask_to_task('sid_2', Actor.Requestor)
        assert not self.task_session._subtask_to_task('sid_2', Actor.Provider)
        assert not self.task_session._subtask_to_task('sid_1', Actor.Requestor)

        self.task_session.task_manager = None
        assert not self.task_session._subtask_to_task('sid_1', Actor.Provider)
        assert not self.task_session._subtask_to_task('sid_2', Actor.Requestor)


class TestSessionWithDB(testutils.DatabaseFixture):
    def setUp(self):
        super(TestSessionWithDB, self).setUp()
        random.seed()
        self.task_session = TaskSession(Mock())

    @patch('golem.task.tasksession.TaskSession.send')
    def test_inform_worker_about_payment(self, send_mock):
        transaction_id = str(uuid.uuid4())
        block_number = random.randint(1, 2 ** 8)
        payment = model.Payment.create(
            subtask=str(uuid.uuid4()),
            payee=str(uuid.uuid4()),
            value=random.randint(1, 10),
            details=model.PaymentDetails(
                tx=transaction_id,
                block_number=block_number,
            )
        )
        self.task_session.inform_worker_about_payment(payment)
        expected = [
            ['subtask_id', payment.subtask],
            ['reward', payment.value],
            ['transaction_id', transaction_id],
            ['block_number', block_number],
        ]
        self.assertEqual(send_mock.call_args[0][0].slots(), expected)

    @patch('golem.task.tasksession.TaskSession.send')
    def test_request_payment(self, send_mock):
        subtask_id = str(uuid.uuid4())
        expected_income = model.ExpectedIncome.create(
            sender_node=str(uuid.uuid4()),
            sender_node_details=None,
            value=random.randint(1, 10),
            subtask=subtask_id,
            task=str(uuid.uuid4())
        )
        self.task_session.request_payment(expected_income)
        expected = [
            ['subtask_id', subtask_id],
        ]
        self.assertEqual(send_mock.call_args[0][0].slots(), expected)

    @patch('golem.task.tasksession.TaskSession.inform_worker_about_payment')
    def test_react_to_subtask_payment_request(self, inform_mock) -> None:
        subtask_id = str(uuid.uuid4())
        msg = message.SubtaskPaymentRequest(subtask_id=subtask_id)
        # Payment does not exist
        self.task_session._react_to_subtask_payment_request(msg)
        inform_mock.assert_not_called()

        # Payment exists
        payment = model.Payment.create(
            subtask=subtask_id,
            payee=str(uuid.uuid4()),
            value=random.randint(1, 10),
            details=model.PaymentDetails()
        )
        self.task_session._react_to_subtask_payment_request(msg)
        inform_mock.assert_called_once_with(payment)


def executor_success(req, success, error):
    success(('filename', 'multihash'))


def executor_recoverable_error(req, success, error):
    error(EnvironmentError())


def executor_error(req, success, error):
    error(Exception())


class TestCreatePackage(unittest.TestCase):
    def setUp(self):
        conn = Mock()
        ts = TaskSession(conn)
        ts.dropped = Mock()
        ts.result_received = Mock()
        ts.send = Mock()
        ts.task_manager = Mock()

        subtask_id = 'xxyyzz'

        res = Mock()
        res.subtask_id = subtask_id
        ts.task_server.get_waiting_task_result.return_value = res

        msg = message.GetTaskResult(subtask_id=subtask_id, raw=b'')

        self.subtask_id = subtask_id
        self.ts = ts
        self.msg = msg

    @patch('golem.task.tasksession.async_run', side_effect=executor_success)
    def test_send_task_result_hash_success(self, _):
        ts = self.ts
        ts._react_to_get_task_result(self.msg)

        assert ts.send.called
        assert not ts.dropped.called

    @patch('golem.task.tasksession.async_run',
           side_effect=executor_recoverable_error)
    def test_send_task_result_hash_recoverable_error(self, _):
        ts = self.ts
        ts._react_to_get_task_result(self.msg)

        assert not ts.send.called
        assert ts.task_server.retry_sending_task_result.called

    @patch('golem.task.tasksession.async_run', side_effect=executor_error)
    def test_send_task_result_hash_unrecoverable_error(self, _):
        ts = self.ts
        ts._react_to_get_task_result(self.msg)

        assert ts.send.called
        assert ts.dropped.called
