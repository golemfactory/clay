import os
from unittest import TestCase
from unittest.mock import patch

from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytaskstate import \
    DummyTaskOptions, DummyTaskDefinition
from golem.core.common import get_golem_path
from golem.resource.dirmanager import list_dir_recursive
from golem.testutils import PEP8MixIn, TempDirFixture


class TestDummyTaskOptions(TestCase):
    def test_option(self):
        opts = DummyTaskOptions()
        assert isinstance(opts, DummyTaskOptions)
        assert isinstance(opts.environment, DummyTaskEnvironment)
        assert opts.subtask_data_size == 128
        assert opts.difficulty == 0xffff0000


class TestDummyTaskStateStyle(TestCase, PEP8MixIn):
    PEP8_FILES = [
        "apps/dummy/task/dummytaskstate.py"
    ]


class TestDummyTaskDefinition(TempDirFixture):
    def test_init(self):
        td = DummyTaskDefinition()
        assert isinstance(td, DummyTaskDefinition)
        assert isinstance(td.options, DummyTaskOptions)
        assert td.options.subtask_data_size == 128
        assert td.options.difficulty == 0xffff0000
        assert td.code_dir == os.path.join(get_golem_path(), "apps", "dummy", "resources", "code_dir")
        for c in list_dir_recursive(td.code_dir):
            assert os.path.isfile(c)
        assert td.result_size == 256
        assert td.out_file_basename == "out"
        assert isinstance(td.resources, set)
        assert td.subtasks_count == 5
        assert td.shared_data_files == ["in.data"]

    def test_add_to_resources(self):
        td = DummyTaskDefinition()
        td.resources = {os.path.join(get_golem_path(), "apps", "dummy", "test_data", "in.data")}
        assert os.path.isfile(list(td.resources)[0])
        with patch("tempfile.mkdtemp", lambda: self.tempdir):
            td.add_to_resources()
            assert os.path.isdir(td.tmp_dir)
            assert isinstance(td.resources, set)
            assert td.tmp_dir == self.tempdir
            assert os.path.isdir(os.path.join(td.tmp_dir, "code"))
            assert os.path.isdir(os.path.join(td.tmp_dir, "data"))
            assert os.path.commonpath(list(td.resources)) == self.tempdir
            assert td.resources == set(list_dir_recursive(td.tmp_dir))
