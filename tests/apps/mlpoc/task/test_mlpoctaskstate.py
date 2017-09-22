import os
from unittest import TestCase
from unittest.mock import patch

from apps.mlpoc.mlpocenvironment import MLPOCTorchEnvironment
from apps.mlpoc.task.mlpoctaskstate import MLPOCTaskDefaults, MLPOCTaskOptions, MLPOCTaskDefinition, ls_R
from golem.core.common import get_golem_path
from golem.testutils import TempDirFixture


class TestMLPOCTaskDefaults(TestCase):
    def test_init(self):
        td = MLPOCTaskDefaults()
        assert isinstance(td, MLPOCTaskDefaults)
        assert isinstance(td.options, MLPOCTaskOptions)
        assert td.code_dir == os.path.join(get_golem_path(), "apps", "mlpoc", "resources", "code_pytorch")


class TestMLPOCTaskOptions(TestCase):
    def test_option(self):
        opts = MLPOCTaskOptions()
        assert isinstance(opts, MLPOCTaskOptions)
        assert isinstance(opts.environment, MLPOCTorchEnvironment)


class TestMLPOCTaskDefinition(TempDirFixture):
    def test_init(self):
        td = MLPOCTaskDefinition()
        assert isinstance(td, MLPOCTaskDefinition)
        assert isinstance(td.options, MLPOCTaskOptions)
        assert td.code_dir == os.path.join(get_golem_path(), "apps", "mlpoc", "resources", "code_pytorch")
        assert isinstance(td.resources, set)

        defaults = MLPOCTaskDefaults()
        tdd = MLPOCTaskDefinition(defaults)
        assert tdd.code_dir == os.path.join(get_golem_path(), "apps", "mlpoc", "resources", "code_pytorch")
        for c in ls_R(tdd.code_dir):
            assert os.path.isfile(c)

    def test_add_to_resources(self):
        td = MLPOCTaskDefinition(MLPOCTaskDefaults())
        td.resources = {os.path.join(get_golem_path(), "apps", "mlpoc", "test_data", "IRIS.csv")}
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
