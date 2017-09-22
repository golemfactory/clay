import os
from unittest import TestCase
from unittest.mock import patch

from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytaskstate import DummyTaskDefaults, DummyTaskOptions, DummyTaskDefinition, ls_R
from golem.core.common import get_golem_path
from golem.testutils import PEP8MixIn, TempDirFixture


class TestDummyTaskDefaults(TestCase):
    def test_init(self):
        td = DummyTaskDefaults()
        assert isinstance(td, DummyTaskDefaults)
        assert isinstance(td.options, DummyTaskOptions)
        assert td.code_dir == os.path.join(get_golem_path(), "apps", "dummy", "resources", "code_dir")


class TestDummyTaskOptions(TestCase):
    def test_option(self):
        opts = DummyTaskOptions()
        assert isinstance(opts, DummyTaskOptions)
        assert isinstance(opts.environment, DummyTaskEnvironment)


class TestDummyTaskStateStyle(TestCase, PEP8MixIn):
    PEP8_FILES = [
        "apps/dummy/task/dummytaskstate.py"
    ]


class TestDummyTaskDefinition(TempDirFixture):
    def test_init(self):
        td = DummyTaskDefinition()
        assert isinstance(td, DummyTaskDefinition)
        assert isinstance(td.options, DummyTaskOptions)
        assert td.code_dir == os.path.join(get_golem_path(), "apps", "dummy", "resources", "code_dir")
        assert isinstance(td.resources, set)

        defaults = DummyTaskDefaults()
        tdd = DummyTaskDefinition(defaults)
        assert tdd.code_dir == os.path.join(get_golem_path(), "apps", "dummy", "resources", "code_dir")
        for c in ls_R(tdd.code_dir):
            assert os.path.isfile(c)

    def test_add_to_resources(self):
        td = DummyTaskDefinition(DummyTaskDefaults())
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
            assert td.resources == set(ls_R(td.tmp_dir))
