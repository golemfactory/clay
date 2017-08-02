import os

from ethereum.utils import denoms
from pathlib import Path
import pickle
import unittest

from mock import Mock, patch
from PIL import Image

from golem.core.common import is_linux
from golem.resource.dirmanager import DirManager
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.task.taskbase import ComputeTaskDef

from apps.core.task.coretask import AcceptClientVerdict, TaskTypeInfo
from apps.dummy.task.dummytask import (
    logger,
    DummyTaskDefaults,
    DummyTaskBuilder,
    DummyTaskTypeInfo
)
from apps.dummy.task.dummytaskstate import DummyTaskDefinition, DummyTaskOptions


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
        #TODO
        self.assert_(True)