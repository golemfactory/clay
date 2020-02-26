import datetime
import sqlite3
import uuid
from unittest import mock

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
import golem_messages
from golem_messages.factories import tasks as tasks_factories

from golem import model
from golem import testutils
from golem.core.common import default_now
from golem.model import default_msg_deadline
from golem.network.transport import msg_queue


class TestMsqQueue(testutils.DatabaseFixture):
    def setUp(self):
        super().setUp()
        self.node_id = str(uuid.uuid4())
        self.msg = tasks_factories.WantToComputeTaskFactory()

    @freeze_time()
    def test_put(self):
        msg_queue.put(self.node_id, self.msg)
        row = model.QueuedMessage.get()
        self.assertEqual(
            row.msg_cls,
            'golem_messages.message.tasks.WantToComputeTask',
        )
        self.assertEqual(str(row.msg_version), golem_messages.__version__)
        self.assertEqual(row.deadline, default_msg_deadline())
        row_msg = row.as_message()
        self.assertEqual(row_msg.slots(), self.msg.slots())
        self.assertIsNone(row_msg.sig)

    def test_get(self):
        msg_queue.put(self.node_id, self.msg)
        msgs = list(msg_queue.get(self.node_id))
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg.slots(), self.msg.slots())
        self.assertEqual(len(list(msg_queue.get(self.node_id))), 0)

    @freeze_time()
    def test_get_timeout(self):
        timeout = datetime.timedelta(seconds=1)
        msg_queue.put(self.node_id, self.msg, timeout)

        with freeze_time(default_now() + timeout):
            msgs = list(msg_queue.get(self.node_id))

        self.assertEqual(len(msgs), 0)
        self.assertEqual(len(list(msg_queue.get(self.node_id))), 0)

    def test_waiting(self):
        node_id2 = str(uuid.uuid4())
        node_id3 = str(uuid.uuid4())
        msg_queue.put(self.node_id, self.msg)
        msg_queue.put(self.node_id, self.msg)
        msg_queue.put(self.node_id, self.msg)
        msg_queue.put(node_id2, self.msg)
        msg_queue.put(node_id3, self.msg)
        waiting = frozenset(msg_queue.waiting())
        self.assertEqual(
            waiting,
            set([
                self.node_id,
                node_id2,
                node_id3,
            ]),
        )

    @mock.patch(
        'peewee.QueryResultWrapper.iterate',
        side_effect=sqlite3.ProgrammingError,
    )
    def test_waiting_programming_error(self, *_args):
        msg_queue.put(self.node_id, self.msg)
        # Error should be handled cleanly inside waiting()
        waiting = frozenset(msg_queue.waiting())
        self.assertEqual(waiting, set())

    @freeze_time()
    def test_waiting_timeout(self):
        timeout = datetime.timedelta(hours=1)
        node_id2 = str(uuid.uuid4())
        node_id_timeout = str(uuid.uuid4())
        msg_queue.put(self.node_id, self.msg)
        msg_queue.put(node_id2, self.msg)
        msg_queue.put(node_id_timeout, self.msg, timeout)

        with freeze_time(default_now() + datetime.timedelta(hours=2)):
            waiting = frozenset(msg_queue.waiting())

        self.assertEqual(
            waiting,
            set([
                self.node_id,
                node_id2
            ]),
        )

    def test_sweep(self):
        def put_explicit_now():
            instance = model.QueuedMessage.from_message(self.node_id, self.msg)
            # peewee/sqlite is freezegun resistant
            instance.created_date = default_now()
            instance.save()
        put_explicit_now()
        msg_queue.sweep()
        self.assertEqual(
            model.QueuedMessage.select().count(),
            1,
        )
        model.QueuedMessage.delete().execute()
        self.assertEqual(
            model.QueuedMessage.select().count(),
            0,
        )
        now = default_now()
        with freeze_time(now-relativedelta(months=6, seconds=1)):
            put_explicit_now()
        msg_queue.sweep()
        self.assertEqual(
            model.QueuedMessage.select().count(),
            0,
        )

    @freeze_time()
    def test_sweep_timeout(self):
        timeout = datetime.timedelta(seconds=1)
        msg_queue.put(self.node_id, self.msg)
        msg_queue.put(self.node_id, self.msg, timeout)

        msg_queue.sweep()
        self.assertEqual(model.QueuedMessage.select().count(), 2)
        with freeze_time(default_now() + datetime.timedelta(minutes=1)):
            msg_queue.sweep()

        self.assertEqual(model.QueuedMessage.select().count(), 1)
