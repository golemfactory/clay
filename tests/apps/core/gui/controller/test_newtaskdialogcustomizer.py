import re

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from mock import Mock, patch

from golem.core.common import is_windows
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from apps.core.gui.controller.newtaskdialogcustomizer import (logger, NewTaskDialogCustomizer)
from apps.core.task.coretask import TaskTypeInfo
from apps.core.task.coretaskstate import TaskDefinition, CoreTaskDefaults, Options
from apps.blender.task.blenderrendertask import BlenderTaskTypeInfo
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition, RendererDefaults


from gui.application import Gui
from gui.applicationlogic import GuiApplicationLogic
from gui.startapp import register_task_types
from gui.view.appmainwindow import AppMainWindow


class TestNewTaskDialogCustomizer(TempDirFixture, LogTestCase):

    def setUp(self):
        super(TestNewTaskDialogCustomizer, self).setUp()
        self.logic = GuiApplicationLogic()
        self.gui = Gui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestNewTaskDialogCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    def test_customizer(self):

        self.logic.client = Mock()
        self.logic.client.config_desc = Mock()
        self.logic.client.config_desc.max_price = 0
        self.logic.client.get_config.return_value = self.logic.client.config_desc
        self.logic.dir_manager = Mock()
        self.logic.dir_manager.root_path = self.path

        tti = TaskTypeInfo("Nice task", TaskDefinition, CoreTaskDefaults(), Mock(),
                           Mock(), Mock(), Mock())
        self.logic.register_new_task_type(tti)
        self.gui.main_window.ui.taskSpecificLayout = Mock()
        self.gui.main_window.ui.taskSpecificLayout.count.return_value = 2
        customizer = NewTaskDialogCustomizer(self.gui.main_window, self.logic)
        self.assertIsInstance(customizer, NewTaskDialogCustomizer)
        assert customizer.gui.ui.showAdvanceNewTaskButton.text() == customizer.SHOW_ADVANCE_BUTTON_MESSAGE[0]
        assert not customizer.gui.ui.advanceNewTaskWidget.isVisible()
        customizer._advance_settings_button_clicked()
        QTest.mouseClick(customizer.gui.ui.showAdvanceNewTaskButton, Qt.LeftButton)

        task_name = "Some Nice Task"
        td = TaskDefinition()
        td.resources = ["/abc/./def", "/ghi/jik"]
        td.main_program_file = "/a/b/c/"
        td.task_name = task_name
        td.main_scene_file = 'a/b/c/d e/file.blend'
        td.task_type = "Nice task"
        td.output_file = 'a/b/c/d e/result.jpeg'
        win_norm_resources = {"\\abc\\def", "\\ghi\\jik"}
        oth_norm_resources = {"/abc/def", "/ghi/jik"}
        customizer.load_task_definition(td)
        if is_windows():
            assert customizer.add_task_resource_dialog_customizer.resources == win_norm_resources
        else:
            assert customizer.add_task_resource_dialog_customizer.resources == oth_norm_resources
        assert customizer.gui.ui.taskNameLineEdit.text() == task_name

        assert td.resources == ["/abc/./def", "/ghi/jik"]
        customizer._read_basic_task_params(td)
        if is_windows():
            assert td.resources == win_norm_resources
        else:
            assert td.resources == oth_norm_resources
        assert td.task_name == task_name

        reg = re.compile('Nice task_[0-2]\d:[0-5]\d:[0-5]\d_20\d\d-[0-1]\d\-[0-3]\d')
        td.task_name = None
        customizer.load_task_definition(td)
        name = "{}".format(customizer.gui.ui.taskNameLineEdit.text())
        assert re.match(reg, name) is not None, "Task name does not match: {}".format(name)

        td.task_name = ""
        customizer.load_task_definition(td)
        name = "{}".format(customizer.gui.ui.taskNameLineEdit.text())
        assert re.match(reg, name) is not None, "Task name does not match: {}".format(name)

    @patch('apps.core.gui.controller.newtaskdialogcustomizer.QFileDialog')
    def test_customizer(self, file_dialog_mock):
        self.logic.client = Mock()
        self.logic.client.config_desc = Mock()
        self.logic.client.config_desc.max_price = 0
        self.logic.client.get_config.return_value = self.logic.client.config_desc
        self.logic.dir_manager = Mock()
        self.logic.dir_manager.root_path = self.path
        self.logic.customizer = Mock()

        register_task_types(self.logic)
        customizer = NewTaskDialogCustomizer(self.gui.main_window, self.logic)
        self.assertIsInstance(customizer, NewTaskDialogCustomizer)

        definition = RenderingTaskDefinition()
        renderer = BlenderTaskTypeInfo(Mock(), Mock())
        assert renderer.name == "Blender"
        assert renderer.options is not None
        definition.task_type = renderer.name
        definition.options = Mock()
        definition.options.use_frames = False
        definition.options.compositing = False
        resources = self.additional_dir_content([3])
        definition.resources = set(resources)
        self.logic.customizer = Mock()
        self.logic.task_types[renderer.name] = renderer
        customizer.load_task_definition(definition)
        with self.assertRaises(TypeError):
            customizer.load_task_definition(None)
        self.assertEqual(len(definition.resources), 3)
        customizer.gui.ui.taskNameLineEdit.setText("NEW NAME")
        definition2 = customizer._query_task_definition()
        self.assertEqual(definition2.task_name, "NEW NAME")
        file_dialog_mock.getOpenFileName.return_value = "/abc/def/ghi"

        definition.task_type = "UNKNOWN"
        with self.assertLogs(logger, level="ERROR"):
            customizer._load_task_type(definition)

        options = Options()
        customizer.set_options(options)
        assert customizer.logic.options == options

        customizer._NewTaskDialogCustomizer__test_task_button_clicked()
        customizer.test_task_computation_finished(True, 103139)
        self.assertEqual(customizer.task_state.definition.estimated_memory, 103139)
        self.assertTrue(customizer.gui.ui.finishButton.isEnabled())
        customizer._show_add_resource_dialog()
        self.assertFalse(customizer.gui.ui.finishButton.isEnabled())

        customizer._open_options()
