from freezegun import freeze_time

from golem.task.verification.queue.backend import DatabaseQueueBackend
from golem.testutils import DatabaseFixture


TASK_ID = 'task_id'
SUBTASK_ID = 'subtask_id'


class TestDatabaseQueueBackend(DatabaseFixture):

    def setUp(self):
        super().setUp()
        self.backend = DatabaseQueueBackend()

    def test_get_empty(self):
        assert self.backend.get() is None

    def test_get_none_priorities(self):
        self.backend.put(f"{TASK_ID}0", f"{SUBTASK_ID}0", priority=None)
        self.backend.put(f"{TASK_ID}1", f"{SUBTASK_ID}1", priority=None)

        assert self.backend.get() is None

    def test_get_mixed_priorities(self):
        self.backend.put(f"{TASK_ID}0", f"{SUBTASK_ID}0", priority=None)
        self.backend.put(f"{TASK_ID}1", f"{SUBTASK_ID}1", priority=2)
        self.backend.put(f"{TASK_ID}3", f"{SUBTASK_ID}3", priority=0)
        self.backend.put(f"{TASK_ID}2", f"{SUBTASK_ID}2", priority=1)
        self.backend.put(f"{TASK_ID}4", f"{SUBTASK_ID}4", priority=None)

        assert self.backend.get() == (f"{TASK_ID}3", f"{SUBTASK_ID}3")
        assert self.backend.get() == (f"{TASK_ID}2", f"{SUBTASK_ID}2")
        assert self.backend.get() == (f"{TASK_ID}1", f"{SUBTASK_ID}1")
        assert self.backend.get() is None

    def test_put_duplicate(self):
        assert self.backend.put(TASK_ID, SUBTASK_ID, priority=None)
        assert not self.backend.put(TASK_ID, SUBTASK_ID, priority=None)

    def test_update_priorities_all_assigned(self):
        self.backend.put(f"{TASK_ID}1", f"{SUBTASK_ID}1", priority=2)
        self.backend.put(f"{TASK_ID}2", f"{SUBTASK_ID}2", priority=1)
        self.backend.update_not_prioritized(lambda: 0)

        assert self.backend.get() == (f"{TASK_ID}2", f"{SUBTASK_ID}2")
        assert self.backend.get() == (f"{TASK_ID}1", f"{SUBTASK_ID}1")
        assert self.backend.get() is None

    def test_update_priorities(self):
        counter = 0

        def priority_fn() -> int:
            nonlocal counter
            counter += 1
            return counter

        with freeze_time('1000'):
            self.backend.put(f"{TASK_ID}0", f"{SUBTASK_ID}0", priority=None)
        with freeze_time('1001'):
            self.backend.put(f"{TASK_ID}1", f"{SUBTASK_ID}1", priority=3)
        with freeze_time('1002'):
            self.backend.put(f"{TASK_ID}2", f"{SUBTASK_ID}2", priority=None)

        self.backend.update_not_prioritized(priority_fn)

        assert self.backend.get() == (f"{TASK_ID}0", f"{SUBTASK_ID}0")
        assert self.backend.get() == (f"{TASK_ID}2", f"{SUBTASK_ID}2")
        assert self.backend.get() == (f"{TASK_ID}1", f"{SUBTASK_ID}1")
        assert self.backend.get() is None
