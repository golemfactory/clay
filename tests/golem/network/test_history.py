# pylint: disable= no-self-use,protected-access
import datetime
import queue
import uuid
import unittest
import unittest.mock as mock

from faker import Faker
from peewee import DataError, PeeweeException, IntegrityError

from golem.model import NetworkMessage, Actor
from golem.network import history
from golem.testutils import DatabaseFixture

from tests.factories import messages as msg_factories

fake = Faker()


def message_count():
    return NetworkMessage.select().count()


class TestMessageHistoryService(DatabaseFixture):

    def setUp(self):
        super().setUp()
        self.service = history.MessageHistoryService()

    def tearDown(self):
        super().tearDown()
        history.MessageHistoryService.instance = None

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

    @mock.patch('golem.model.NetworkMessage.save')
    def test_add_sync_fail(self, save):
        self.service._save_queue = mock.Mock()
        msg_dict = self._build_dict(None, None)

        save.side_effect = DataError

        self.service.add_sync(msg_dict)
        assert not self.service._save_queue.put.called
        assert message_count() == 0

        save.side_effect = PeeweeException

        self.service.add_sync(msg_dict)
        assert self.service._save_queue.put.called
        assert message_count() == 0

    def test_add_sync_success(self):
        msg_dict = self._build_dict(None, None)
        self.service.add_sync(msg_dict)
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
        msg = self._build_dict(None, None)

        self.service.add_sync(msg)
        self.service._remove_queue = mock.Mock()

        assert message_count() == 1

        with mock.patch('peewee.DeleteQuery.execute', side_effect=DataError):
            self.service.remove_sync(msg['task'])
            assert not self.service._remove_queue.put.called
            assert message_count() == 1

        with mock.patch('peewee.DeleteQuery.execute',
                        side_effect=PeeweeException):
            self.service.remove_sync(msg['task'])
            assert self.service._remove_queue.put.called
            assert message_count() == 1

        self.service.remove_sync(msg['task'], subtask=str(uuid.uuid4()))
        assert message_count() == 1
        self.service.remove_sync(msg['task'], subtask=msg['subtask'])
        assert message_count() == 0

    def test_get_sync(self):
        msgs = [
            self._build_dict("task", None),
            self._build_dict("task", None),
            self._build_dict("task", None)
        ]

        for msg in msgs:
            self.service.add_sync(msg)
        assert message_count() == 3

        result = self.service.get_sync(task="task", subtask="unknown")
        assert not result

        result = self.service.get_sync(task="task")
        assert len(result) == 3

        result = self.service.get_sync(task="task", subtask=msgs[0]['subtask'])
        assert len(result) == 1

    def test_build_clauses(self):
        clauses = self.service.build_clauses(task="task", subtask="subtask",
                                             unknown="unknown")
        assert len(clauses) == 2
        assert all(prop in clauses for prop in ['task', 'subtask'])

    @mock.patch(
        'golem.network.history.MessageHistoryService.QUEUE_TIMEOUT',
        0.1,
    )
    def test_start_stop(self, *_):
        self.service._loop = mock.Mock()

        assert not self.service.running
        self.service.start()
        assert self.service.running
        self.service._thread.join(1.)
        self.service.stop()
        assert not self.service.running

        assert self.service._loop.called

    @mock.patch('threading.Thread')
    def test_multiple_starts(self, *_):
        self.service.start()
        assert self.service._thread.start.called

        self.service._thread.reset_mock()
        self.service._thread.is_alive.return_value = True
        self.service.start()
        assert not self.service._thread.start.called

    def test_sweep(self):
        msgs = [
            self._build_dict(),
            self._build_dict(),
            self._build_dict()
        ]

        for msg in msgs:
            self.service.add_sync(msg)

        assert message_count() == 3
        self.service._sweep()
        assert message_count() == 3

        result = NetworkMessage.select() \
            .where(NetworkMessage.task == msgs[0]['task']) \
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

    def test_loop_sweep(self):
        self.service._sweep = mock.Mock()
        self.service._queue_timeout = 0.1

        self.service._loop()
        assert self.service._sweep.called

        self.service._sweep.reset_mock()
        self.service._loop()
        assert not self.service._sweep.called

    def test_loop_add_sync(self):
        self.service._sweep = mock.Mock()
        self.service._queue_timeout = 0.1
        self.service.add_sync = mock.Mock()

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

    def test_loop_remove_sync(self):
        self.service._sweep = mock.Mock()
        self.service._queue_timeout = 0.1
        self.service.remove_sync = mock.Mock()

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


@mock.patch("golem.network.history.MessageHistoryService.add")
class TestAdd(unittest.TestCase):
    def setUp(self):
        self.service = history.MessageHistoryService().instance
        self.msg = msg_factories.TaskToCompute()

    def tearDown(self):
        super().tearDown()
        history.MessageHistoryService.instance = None

    def test_no_service(self, add_mock):
        history.MessageHistoryService.instance = None
        history.add(
            msg=self.msg,
            node_id=fake.binary(length=64),
            local_role=fake.random_element(Actor),
            remote_role=fake.random_element(Actor),
        )
        add_mock.assert_not_called()

    @mock.patch("golem.network.history.message_to_model", side_effect=Exception)
    def test_model_failed(self, model_mock, add_mock):
        history.add(
            msg=self.msg,
            node_id=fake.binary(length=64),
            local_role=fake.random_element(Actor),
            remote_role=fake.random_element(Actor),
        )
        model_mock.assert_called_once()
        add_mock.assert_not_called()

    def test_service_add_failed(self, add_mock):
        add_mock.side_effect = Exception
        history.add(
            msg=self.msg,
            node_id=fake.binary(length=64),
            local_role=fake.random_element(Actor),
            remote_role=fake.random_element(Actor),
        )
        add_mock.assert_called_once()

    @mock.patch("golem.network.history.message_to_model")
    def test_success(self, model_mock, add_mock):
        model_mock.return_value = model = {}
        node_id = fake.binary(length=64)
        local_role = fake.random_element(Actor)
        remote_role = fake.random_element(Actor)
        history.add(
            msg=self.msg,
            node_id=node_id,
            local_role=local_role,
            remote_role=remote_role,
        )
        model_mock.assert_called_once_with(
            msg=self.msg,
            node_id=node_id,
            local_role=local_role,
            remote_role=remote_role,
        )
        add_mock.assert_called_once_with(model)


class TestMessageToModel(unittest.TestCase):
    def setUp(self):
        self.msg = msg_factories.TaskToCompute()

    def test_basic(self):
        node_id = fake.binary(length=64)
        local_role = fake.random_element(Actor)
        remote_role = fake.random_element(Actor)
        result = history.message_to_model(
            msg=self.msg,
            node_id=node_id,
            local_role=local_role,
            remote_role=remote_role,
        )
        expected = {
            'task': self.msg.task_id,
            'subtask': self.msg.subtask_id,
            'node': node_id,
            'msg_date': mock.ANY,
            'msg_cls': 'TaskToCompute',
            'msg_data': mock.ANY,
            'local_role': local_role,
            'remote_role': remote_role,
        }
        self.assertEqual(result, expected)


class TestNetworkMessage(DatabaseFixture):

    def setUp(self):
        super().setUp()
        self.param_kwargs = dict(node='node', task=None, subtask=None)

    def test_save(self):
        NetworkMessage(
            local_role=Actor.Provider,
            remote_role=Actor.Requestor,

            msg_date=datetime.time(),
            msg_cls='cls',
            msg_data=b'bytes',

            **self.param_kwargs
        ).save()

    def test_save_failing_role_constraints(self):
        msg_kwargs = dict(msg_date=datetime.time(),
                          msg_cls='cls',
                          msg_data=b'bytes')
        self.param_kwargs.update(msg_kwargs)

        with self.assertRaises(TypeError):
            NetworkMessage(
                local_role=None,
                remote_role=Actor.Requestor,
                **self.param_kwargs
            ).save()

        with self.assertRaises(TypeError):
            NetworkMessage(
                local_role=Actor.Provider,
                remote_role=None,
                **self.param_kwargs
            ).save()

    def test_save_failing_msg_constraints(self):
        role_kwargs = dict(local_role=Actor.Provider,
                           remote_role=Actor.Requestor)
        self.param_kwargs.update(role_kwargs)

        with self.assertRaises(IntegrityError):
            NetworkMessage(
                msg_date=None,
                msg_cls='cls',
                msg_data=b'bytes',
                **self.param_kwargs
            ).save()

        with self.assertRaises(IntegrityError):
            NetworkMessage(
                msg_date=datetime.time(),
                msg_cls=None,
                msg_data=b'bytes',
                **self.param_kwargs
            ).save()

        with self.assertRaises(IntegrityError):
            NetworkMessage(
                msg_date=datetime.time(),
                msg_cls='cls',
                msg_data=None,
                **self.param_kwargs
            ).save()
