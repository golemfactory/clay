from apps.dummy.task.dummytask import (
    DummyTaskDefaults,
    DummyTaskBuilder
)
from apps.dummy.task.dummytaskstate import DummyTaskDefinition
from golem.resource.dirmanager import DirManager
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase


class TestDummyTask(TempDirFixture, LogTestCase, PEP8MixIn):
    PEP8_FILES = [
        'apps/dummy/task/dummytask.py',
    ]

    def get_test_dummy_task(self, defaults):
        td = DummyTaskDefinition(defaults)
        dm = DirManager(self.path)
        db = DummyTaskBuilder("MyNodeName", td, self.path, dm)
        return db.build()

    def test___init__(self):
        dd = DummyTaskDefaults()
        # TODO
        self.assert_(True)
