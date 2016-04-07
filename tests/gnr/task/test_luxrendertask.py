import unittest
import os

from golem.tools.testdirfixture import TestDirFixture
from golem.tools.assertlogs import LogTestCase

from gnr.renderingtaskstate import RenderingTaskDefinition
from gnr.task.luxrendertask import LuxRenderDefaults, LuxRenderTaskBuilder, LuxRenderOptions, logger


class TestLuxRenderDefaults(unittest.TestCase):
    def test_init(self):
        ld = LuxRenderDefaults()
        self.assertTrue(os.path.isfile(ld.main_program_file))


class TestLuxRenderTaskBuilder(TestDirFixture, LogTestCase):
    def test_luxtask(self):
        td = RenderingTaskDefinition()
        lro = LuxRenderOptions()
        td.renderer_options = lro
        lb = LuxRenderTaskBuilder("ABC", td, self.path)
        luxtask = lb.build()

        with self.assertLogs(logger, level="WARNING"):
            luxtask.after_test({}, self.path)



