import datetime
import uuid

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
import golem_messages
from golem_messages.factories import tasks as tasks_factories

from golem import model
from golem import testutils
from golem.network.transport import msg_queue

class TestMsqQueue(testutils.DatabaseFixture):
    def setUp(self):
        super().setUp()
        self.node_id = str(uuid.uuid4())
        self.msg = tasks_factories.WantToComputeTaskFactory()

    def test_put(self):
        msg_queue.put(self.node_id, self.msg)
        row = model.QueuedMessage.get()
        self.assertEqual(
            row.msg_cls,
            'golem_messages.message.tasks.WantToComputeTask',
        )
        self.assertEqual(str(row.msg_version), golem_messages.__version__)
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

    def test_sweep(self):
        def put_explicit_now():
            instance = model.QueuedMessage.from_message(self.node_id, self.msg)
            # peewee/sqlite is freezegun resistant
            instance.created_date = datetime.datetime.now()
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
        now = datetime.datetime.now()
        with freeze_time(now-relativedelta(months=6, seconds=1)):
            put_explicit_now()
        msg_queue.sweep()
        self.assertEqual(
            model.QueuedMessage.select().count(),
            0,
        )
