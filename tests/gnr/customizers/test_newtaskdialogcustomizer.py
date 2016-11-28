import re

from PyQt4.QtCore import Qt
from PyQt4.QtTest import QTest
from mock import Mock

from gui.startapp import register_rendering_task_types

from golem.core.common import is_windows
from golem.testutils import TempDirFixture

from gui.application import GNRGui
from gnr.customizers.newtaskdialogcustomizer import NewTaskDialogCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.gnrtaskstate import GNRTaskDefinition
from gnr.ui.appmainwindow import AppMainWindow


class TestNewTaskDialogCustomizer(TempDirFixture):

    def setUp(self):
        super(TestNewTaskDialogCustomizer, self).setUp()
        self.logic = RenderingApplicationLogic()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestNewTaskDialogCustomizer, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    def test_customizer(self):

        self.logic.client = Mock()
        self.logic.client.config_desc = Mock()
        self.logic.client.config_desc.max_price = 0
        self.logic.client.get_config.return_value = self.logic.client.config_desc
        self.logic.dir_manager = Mock()
        self.logic.dir_manager.root_path = self.path

        register_rendering_task_types(self.logic)
        customizer = NewTaskDialogCustomizer(self.gnrgui.main_window, self.logic)
        self.assertIsInstance(customizer, NewTaskDialogCustomizer)
        customizer.gui.ui.taskTypeComboBox.addItem("Blender")
        customizer.gui.ui.taskTypeComboBox.setCurrentIndex(0)
        assert customizer.gui.ui.showAdvanceNewTaskButton.text() == customizer.SHOW_ADVANCE_BUTTON_MESSAGE[0]
        assert not customizer.gui.ui.advanceNewTaskWidget.isVisible()
        customizer._advance_settings_button_clicked()
        QTest.mouseClick(customizer.gui.ui.showAdvanceNewTaskButton, Qt.LeftButton)

        task_name = "Some Nice Task"
        td = GNRTaskDefinition()
        td.resources = ["/abc/./def", "/ghi/jik"]
        td.main_program_file = "/a/b/c/"
        td.task_name = task_name
        td.main_scene_file = 'a/b/c/d e/file.blend'
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

        reg = re.compile('Blender_[0-2]\d:[0-5]\d:[0-5]\d_20\d\d-[0-1]\d\-[0-3]\d')
        td.task_name = None
        customizer.load_task_definition(td)
        name = "{}".format(customizer.gui.ui.taskNameLineEdit.text())
        assert re.match(reg, name) is not None, "Task name does not match: {}".format(name)

        td.task_name = ""
        customizer.load_task_definition(td)
        name = "{}".format(customizer.gui.ui.taskNameLineEdit.text())
        assert re.match(reg, name) is not None, "Task name does not match: {}".format(name)
