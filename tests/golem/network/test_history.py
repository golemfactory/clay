import datetime
import queue
import uuid
from unittest.mock import Mock, patch

from golem_messages import message
from peewee import DataError, PeeweeException

from golem.model import NetworkMessage, Actor
from golem.network.history import MessageHistoryService
from golem.testutils import DatabaseFixture


def message_count():
    return len(NetworkMessage.select().execute())


class TestMessageHistoryService(DatabaseFixture):

    def setUp(self):
        super().setUp()
        self.service = MessageHistoryService()

    @staticmethod
    def _build_raise(cls):
        def _raise(*_a, **_kw):
            raise cls()
        return Mock(side_effect=_raise)

    @staticmethod
    def _build_msg(task=None, subtask=None):
        return NetworkMessage(
            task=task or str(uuid.uuid4()),
            subtask=subtask or str(uuid.uuid4()),
            node=str(uuid.uuid4()),

            msg_date=datetime.datetime.now(),
            msg_cls=message.MessageHello.__class__.__name__,
            msg_data=b'0' * 64,

            local_role=Actor.Provider,
            remote_role=Actor.Requestor,
        )

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

        with patch.object(msg, 'save',
                          side_effect=self._build_raise(DataError)):
            self.service.add_sync(msg)
            assert not self.service._save_queue.put.called
            assert message_count() == 0

        with patch.object(msg, 'save',
                          side_effect=self._build_raise(PeeweeException)):
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

        with patch('peewee.DeleteQuery.execute',
                   side_effect=self._build_raise(DataError)):
            self.service.remove_sync(msg.task)
            assert not self.service._remove_queue.put.called
            assert message_count() == 1

        with patch('peewee.DeleteQuery.execute',
                   side_effect=self._build_raise(PeeweeException)):
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
        assert len(result) == 0

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

        self.service.start()
        self.service.join(1.)
        self.service.stop()

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

    @patch('golem.network.history.MessageHistoryService.QUEUE_TIMEOUT', 0.1)
    def test_loop_sweep(self, *_):
        self.service._sweep = Mock()

        self.service._loop()
        assert self.service._sweep.called

        self.service._sweep.reset_mock()
        self.service._loop()
        assert not self.service._sweep.called

    @patch('golem.network.history.MessageHistoryService.QUEUE_TIMEOUT', 0.1)
    def test_loop_add_sync(self, *_):
        self.service._sweep = Mock()
        self.service.add_sync = Mock()

        # No message
        self.service._loop()
        assert not self.service.add_sync.called

        # Add message
        msg = self._build_msg()
        self.service._save_queue.put(msg)

        # With message
        self.service._loop()
        assert self.service.add_sync.called

        # No message again, since it was popped from the queue
        self.service.add_sync.reset_mock()
        self.service._loop()
        assert not self.service.add_sync.called

    @patch('golem.network.history.MessageHistoryService.QUEUE_TIMEOUT', 0.1)
    def test_loop_remove_sync(self, *_):
        self.service._sweep = Mock()
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
