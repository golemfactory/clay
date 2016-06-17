from unittest import TestCase

from PyQt4.QtCore import Qt
from PyQt4.QtTest import QTest
from mock import Mock

from golem.core.common import is_windows

from gnr.application import GNRGui
from gnr.customizers.newtaskdialogcustomizer import NewTaskDialogCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.gnrstartapp import register_rendering_task_types
from gnr.gnrtaskstate import GNRTaskDefinition
from gnr.ui.appmainwindow import AppMainWindow


class TestNewTaskDialogCustomizer(TestCase):
    def test_customizer(self):
        gnrgui = GNRGui(Mock(), AppMainWindow)
        logic = RenderingApplicationLogic()
        logic.client = Mock()
        register_rendering_task_types(logic)
        customizer = NewTaskDialogCustomizer(gnrgui.main_window, logic)
        self.assertIsInstance(customizer, NewTaskDialogCustomizer)
        assert customizer.gui.ui.showAdvanceNewTaskButton.text() == customizer.SHOW_ADVANCE_BUTTON_MESSAGE[0]
        assert not customizer.gui.ui.advanceNewTaskWidget.isVisible()
        customizer._advance_settings_button_clicked()
        QTest.mouseClick(customizer.gui.ui.showAdvanceNewTaskButton, Qt.LeftButton)

        td = GNRTaskDefinition()
        td.resources = ["/abc/./def", "/ghi/jik"]
        td.main_program_file = "/a/b/c/"
        win_norm_resources = {"\\abc\\def", "\\ghi\\jik"}
        oth_norm_resources = {"/abc/def", "/ghi/jik"}
        customizer.load_task_definition(td)
        if is_windows():
            assert customizer.add_task_resource_dialog_customizer.resources == win_norm_resources
        else:
            assert customizer.add_task_resource_dialog_customizer.resources == oth_norm_resources

        assert td.resources == ["/abc/./def", "/ghi/jik"]
        customizer._read_basic_task_params(td)
        if is_windows():
            assert td.resources == win_norm_resources
        else:
            assert td.resources == oth_norm_resources


        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()
