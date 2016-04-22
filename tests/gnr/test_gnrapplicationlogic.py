import os
import time

from mock import Mock

from golem.task.taskbase import TaskBuilder, Task, ComputeTaskDef
from golem.tools.testdirfixture import TestDirFixture
from gnr.application import GNRGui
from gnr.customizers.renderingadmmainwindowcustomizer import RenderingAdmMainWindowCustomizer
from gnr.gnrapplicationlogic import GNRApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow


class TTask(Task):
    def __init__(self):
        Task.__init__(self, Mock(), Mock())
        self.src_code = ""
        self.extra_data = {}
        self.test_finished = False
        self.results = None
        self.tmp_dir = None

    def query_extra_data_for_test_task(self):
        ctd = ComputeTaskDef()
        ctd.subtask_id = "xxyyzz"
        ctd.task_id = "xyz"
        ctd.working_directory = self.header.root_path
        ctd.src_code = self.src_code
        ctd.extra_data = self.extra_data
        ctd.short_description = ""
        return ctd

    def after_test(self, results, tmp_dir):
        self.test_finished = True
        self.results = results
        self.tmp_dir = tmp_dir


class TTaskBuilder(TaskBuilder):

    def __init__(self, path):
        self.path = path
        self.src_code = "output = {'data': n, 'result_type': 0}"
        self.extra_data = {"n": 421}

    def build(self):
        t = TTask()
        t.header.node_name = "node1"
        t.header.task_id = "xyz"
        t.header.root_path = self.path
        t.src_code = self.src_code
        t.extra_data = self.extra_data
        return t


class TestGNRApplicationLogic(TestDirFixture):

    def test_root_path(self):
        logic = GNRApplicationLogic()
        self.assertTrue(os.path.isdir(logic.root_path))

    def test_run_test_task(self):
        logic = GNRApplicationLogic()
        logic.client = Mock()
        gnrgui = GNRGui(Mock(), AppMainWindow)
        logic.client.datadir = self.path
        logic.customizer = RenderingAdmMainWindowCustomizer(gnrgui.main_window, logic)
        logic.customizer.new_task_dialog_customizer = Mock()
        ts = Mock()
        files = self.additional_dir_content([1])
        ts.definition.main_program_file = files[0]
        ts.definition.renderer = "TESTTASK"
        task_type = Mock()
        ttb = TTaskBuilder(self.path)
        task_type.task_builder_type.return_value = ttb
        logic.task_types["TESTTASK"] = task_type
        logic.run_test_task(ts)
        time.sleep(0.5)
        success = logic.customizer.new_task_dialog_customizer.test_task_computation_finished.call_args[0][0]
        self.assertEqual(success, True)
        ttb.src_code = "raise Exception('some error')"
        logic.run_test_task(ts)
        time.sleep(0.5)
        success = logic.customizer.new_task_dialog_customizer.test_task_computation_finished.call_args[0][0]
        self.assertEqual(success, False)
        ttb.src_code = "print 'hello'"
        logic.run_test_task(ts)
        time.sleep(0.5)
        success = logic.customizer.new_task_dialog_customizer.test_task_computation_finished.call_args[0][0]
        self.assertEqual(success, False)

        prev_call_count = logic.customizer.new_task_dialog_customizer.task_settings_changed.call_count
        logic.task_settings_changed()
        assert logic.customizer.new_task_dialog_customizer.task_settings_changed.call_count > prev_call_count

        logic.tasks["xyz"] = ts
        logic.clone_task("xyz")

        assert logic.customizer.new_task_dialog_customizer.load_task_definition.call_args[0][0] == ts.definition

        gnrgui.app.deleteLater()
