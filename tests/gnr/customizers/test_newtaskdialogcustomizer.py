from unittest import TestCase

from mock import Mock

from gnr.application import GNRGui
from gnr.customizers.newtaskdialogcustomizer import NewTaskDialogCustomizer
from gnr.gnradmapplicationlogic import GNRAdmApplicationLogic
from gnr.gnrstartapp import register_task_types
from gnr.ui.administrationmainwindow import AdministrationMainWindow
from gnr.ui.dialog import NewTaskDialog


class TestNewTaskDialogCustomizer(TestCase):
    def test_customizer(self):
        logic = GNRAdmApplicationLogic()
        logic.client = Mock()
        register_task_types(logic)
        gnrgui = GNRGui(Mock(), AdministrationMainWindow)
        customizer = NewTaskDialogCustomizer(NewTaskDialog(gnrgui.main_window.window), logic)
        self.assertIsInstance(customizer, NewTaskDialogCustomizer)
