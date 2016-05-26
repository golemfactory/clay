from unittest import TestCase

from PyQt4.QtCore import Qt
from PyQt4.QtTest import QTest
from mock import Mock

from gnr.application import GNRGui
from gnr.customizers.newtaskdialogcustomizer import NewTaskDialogCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.gnrstartapp import register_rendering_task_types
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

        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()
