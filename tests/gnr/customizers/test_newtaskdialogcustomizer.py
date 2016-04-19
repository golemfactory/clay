from unittest import TestCase

from mock import Mock

from gnr.application import GNRGui
from gnr.customizers.newtaskdialogcustomizer import NewTaskDialogCustomizer
from gnr.gnradmapplicationlogic import GNRAdmApplicationLogic
from gnr.gnrstartapp import register_task_types
from gnr.ui.appmainwindow import AppMainWindow


class TestNewTaskDialogCustomizer(TestCase):
    def test_customizer(self):
        gnrgui = GNRGui(Mock(), AppMainWindow)
        logic = GNRAdmApplicationLogic()
        logic.client = Mock()
        register_task_types(logic)
        customizer = NewTaskDialogCustomizer(gnrgui.main_window, logic)
        self.assertIsInstance(customizer, NewTaskDialogCustomizer)
        gnrgui.app.deleteLater()
