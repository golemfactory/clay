import unittest
import os
from mock import Mock

from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.task.taskbase import ComputeTaskDef

from apps.lux.task.luxrendertask import LuxRenderDefaults, LuxRenderTaskBuilder, LuxRenderOptions, logger
from apps.rendering.task.renderingtask import AcceptClientVerdict

from gnr.renderingtaskstate import RenderingTaskDefinition


class TestLuxRenderDefaults(unittest.TestCase):
    def test_init(self):
        ld = LuxRenderDefaults()
        self.assertTrue(os.path.isfile(ld.main_program_file))


class TestLuxRenderTaskBuilder(TestDirFixture, LogTestCase):

    def test_luxtask(self):
        td = RenderingTaskDefinition()
        lro = LuxRenderOptions()
        td.renderer_options = lro
        dm = DirManager(self.path)
        lb = LuxRenderTaskBuilder("ABC", td, self.path, dm)
        luxtask = lb.build()

        self.__after_test_errors(luxtask)

        self.__queries(luxtask)

    def test_query_extra_data(self):
        td = RenderingTaskDefinition()
        lro = LuxRenderOptions()
        td.renderer_options = lro
        dm = DirManager(self.path)
        lb = LuxRenderTaskBuilder("ABC", td, self.path, dm)
        luxtask = lb.build()
        luxtask._get_scene_file_rel_path = Mock()
        luxtask._get_scene_file_rel_path.return_value = os.path.join(self.path, 'scene')
        luxtask.main_program_file = os.path.join(self.path, 'program.py')

        luxtask._accept_client = Mock()
        luxtask._accept_client.return_value = AcceptClientVerdict.ACCEPTED

        result = luxtask.query_extra_data(0)
        assert result.ctd is not None
        assert not result.should_wait

        luxtask._accept_client.return_value = AcceptClientVerdict.SHOULD_WAIT

        result = luxtask.query_extra_data(0)
        assert result.ctd is None
        assert result.should_wait

        luxtask._accept_client.return_value = AcceptClientVerdict.REJECTED

        result = luxtask.query_extra_data(0)
        assert result.ctd is None
        assert not result.should_wait

    def __after_test_errors(self, luxtask):
        with self.assertLogs(logger, level="WARNING"):
            luxtask.after_test({}, self.path)
        open(os.path.join(self.path, "sth.flm"), 'w').close()
        luxtask.after_test({}, self.path)
        prev_tmp_dir = luxtask.tmp_dir
        luxtask.tmp_dir = "/dev/null/:errors?"
        with self.assertLogs(logger, level="WARNING"):
            luxtask.after_test({}, self.path)
        luxtask.tmp_dir = prev_tmp_dir
        assert os.path.isfile(os.path.join(luxtask.tmp_dir, "test_result.flm"))

    def __queries(self, luxtask):
        luxtask.collected_file_names["xxyyzz"] = "xxyyzzfile"
        luxtask.collected_file_names["abcd"] = "abcdfile"
        ctd = luxtask.query_extra_data_for_final_flm()
        self.assertIsInstance(ctd, ComputeTaskDef)
        assert ctd.src_code is not None
        assert ctd.extra_data['output_flm'] == luxtask.output_file
        assert set(ctd.extra_data['flm_files']) == {"xxyyzzfile", "abcdfile"}






