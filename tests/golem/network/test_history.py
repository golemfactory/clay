import datetime
import queue
import uuid
from unittest.mock import Mock, patch

from golem_messages import message
from peewee import DataError, PeeweeException

from golem.model import NetworkMessage, Actor
from golem.network.history import MessageHistoryService, record_history, \
    IMessageHistoryProvider, requestor_history, provider_history
from golem.testutils import DatabaseFixture


def message_count():
    return NetworkMessage.select().count()


def mock_sign(*_):
    return b'\0' * message.Message.SIG_LEN


class TestMessageHistoryService(DatabaseFixture):

    def setUp(self):
        super().setUp()
        self.service = MessageHistoryService()

    def tearDown(self):
        super().tearDown()
        MessageHistoryService.instance = None

    @staticmethod
    def _build_dict(task=None, subtask=None):
        return dict(
            task=task or str(uuid.uuid4()),
            subtask=subtask or str(uuid.uuid4()),
            node=str(uuid.uuid4()),

            msg_date=datetime.datetime.now(),
            msg_cls='Hello',
            msg_data=b'0' * 64,

            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )

    @classmethod
    def _build_msg(cls, task=None, subtask=None):
        return NetworkMessage(**cls._build_dict(task, subtask))

    def test_add(self):
        msg = self._build_msg()

        self.service.add(msg)
        assert self.service._save_queue.get(block=False) is msg

        self.service.add(None)
        with self.assertRaises(queue.Empty):
            self.service._save_queue.get(block=False)

    def test_add_sync(self):
        self.service._save_queue = Mock()
        msg = self._build_msg()

        with patch.object(msg, 'save', side_effect=DataError):
            self.service.add_sync(msg)
            assert not self.service._save_queue.put.called
            assert message_count() == 0

        with patch.object(msg, 'save', side_effect=PeeweeException):
            self.service.add_sync(msg)
            assert self.service._save_queue.put.called
            assert message_count() == 0

        self.service.add_sync(msg)
        assert message_count() == 1

    def test_remove(self):
        task = str(uuid.uuid4())
        params = dict(subtask=str(uuid.uuid4()))

        self.service.remove(task, **params)
        assert self.service._remove_queue.get(block=False) == (task, params)

        self.service.remove(None)
        with self.assertRaises(queue.Empty):
            self.service._remove_queue.get(block=False)

    def test_remove_sync(self):
        msg = self._build_msg()

        self.service.add_sync(msg)
        self.service._remove_queue = Mock()

        assert message_count() == 1

        with patch('peewee.DeleteQuery.execute', side_effect=DataError):
            self.service.remove_sync(msg.task)
            assert not self.service._remove_queue.put.called
            assert message_count() == 1

        with patch('peewee.DeleteQuery.execute', side_effect=PeeweeException):
            self.service.remove_sync(msg.task)
            assert self.service._remove_queue.put.called
            assert message_count() == 1

        self.service.remove_sync(msg.task, subtask=str(uuid.uuid4()))
        assert message_count() == 1
        self.service.remove_sync(msg.task, subtask=msg.subtask)
        assert message_count() == 0

    def test_get_sync(self):
        msgs = [
            self._build_msg(task="task"),
            self._build_msg(task="task"),
            self._build_msg(task="task")
        ]

        for msg in msgs:
            self.service.add_sync(msg)
        assert message_count() == 3

        result = self.service.get_sync(task="task", subtask="unknown")
        assert not result

        result = self.service.get_sync(task="task")
        assert len(result) == 3

        result = self.service.get_sync(task="task", subtask=msgs[0].subtask)
        assert len(result) == 1

    def test_build_clauses(self):
        clauses = self.service.build_clauses(task="task", subtask="subtask",
                                             unknown="unknown")
        assert len(clauses) == 2
        assert all(prop in clauses for prop in ['task', 'subtask'])

    @patch('golem.network.history.MessageHistoryService.QUEUE_TIMEOUT', 0.1)
    def test_start_stop(self, *_):
        self.service._loop = Mock()

        assert not self.service.running
        self.service.start()
        assert self.service.running
        self.service.join(1.)
        self.service.stop()
        assert not self.service.running

        assert self.service._loop.called

    def test_sweep(self):
        msgs = [
            self._build_msg(),
            self._build_msg(),
            self._build_msg()
        ]

        for msg in msgs:
            self.service.add_sync(msg)

        assert message_count() == 3
        self.service._sweep()
        assert message_count() == 3

        result = NetworkMessage.select() \
            .where(NetworkMessage.task == msgs[0].task) \
            .execute()

        msg = list(result)[0]
        msg.msg_date = (
            datetime.datetime.now()
            - self.service.MESSAGE_LIFETIME
            - datetime.timedelta(hours=5)
        )
        msg.save()

        self.service._sweep()
        assert message_count() == 2

    def test_loop_sweep(self, *_):
        self.service._sweep = Mock()
        self.service._queue_timeout = 0.1

        self.service._loop()
        assert self.service._sweep.called

        self.service._sweep.reset_mock()
        self.service._loop()
        assert not self.service._sweep.called

    def test_loop_add_sync(self, *_):
        self.service._sweep = Mock()
        self.service._queue_timeout = 0.1
        self.service.add_sync = Mock()

        # No message
        self.service._loop()
        assert not self.service.add_sync.called

        # Add message
        msg = self._build_dict()
        self.service._save_queue.put(msg)

        # With message
        self.service._loop()
        assert self.service.add_sync.called

        # No message again, since it was popped from the queue
        self.service.add_sync.reset_mock()
        self.service._loop()
        assert not self.service.add_sync.called

    def test_loop_remove_sync(self, *_):
        self.service._sweep = Mock()
        self.service._queue_timeout = 0.1
        self.service.remove_sync = Mock()

        # No tuple
        self.service._loop()
        assert not self.service.remove_sync.called

        # Add tuple
        task = str(uuid.uuid4())
        props = dict(subtask=str(uuid.uuid4()))
        self.service._remove_queue.put((task, props))

        # With tuple
        self.service._loop()
        assert self.service.remove_sync.called

        # Not tuple again, since it was popped from the queue
        self.service.remove_sync.reset_mock()
        self.service._loop()
        assert not self.service.remove_sync.called


class TestMessageHistoryProvider(DatabaseFixture):

    def tearDown(self):
        super().tearDown()
        MessageHistoryService.instance = None

    def test_invalid_class(self):
        with self.assertRaises(AttributeError):

            class Invalid:
                @record_history(local_role=Actor.Provider,
                                remote_role=Actor.Requestor)
                def method(self, msg):
                    print('Got', msg)

            invalid = Invalid()
            invalid.method(None)

    def test_record_history(self):
        service = MessageHistoryService().instance

        class Provider(IMessageHistoryProvider):

            def __init__(self):
                self.key_id = 'a0b1c2'

            def message_to_model(self, msg, local_role, remote_role):
                return dict(key='value')

            @requestor_history
            def react_to_report_computed_task(self, *_):
                pass

            @provider_history
            def react_to_task_to_compute(self, *_):
                pass

        provider = Provider()

        msg_hello = message.Hello(raw=b'\0')
        msg_request = message.WantToComputeTask(task_id='t', raw=b'\0')
        msg_result = message.ReportComputedTask(subtask_id='s', raw=b'\0')

        NetworkMessage.delete().execute()

        # Resolve node_id
        assert service._save_queue.qsize() == 0
        provider.react_to_task_to_compute(msg_request)
        assert service._save_queue.qsize() == 1

        service._save_queue = queue.Queue()

        # Also resolve task_id using the interface
        assert service._save_queue.qsize() == 0
        provider.react_to_report_computed_task(msg_result)
        assert service._save_queue.qsize() == 1

        service._save_queue = queue.Queue()

        # Logs an error when model is not available
        assert service._save_queue.qsize() == 0
        provider.message_to_model = Mock(return_value=None)
        provider.react_to_task_to_compute(msg_hello)
        assert service._save_queue.qsize() == 0
