from unittest import TestCase

from golem.task.taskstate import SubtaskState

from gui.application import Gui
from gui.controller.subtaskdetailsdialogcustomizer import SubtaskDetailsDialogCustomizer
from gui.applicationlogic import GuiApplicationLogic
from gui.view.appmainwindow import AppMainWindow
from gui.view.dialog import SubtaskDetailsDialog


class TestSubtaskDetailsDialogCustomizer(TestCase):

    def setUp(self):
        super(TestSubtaskDetailsDialogCustomizer, self).setUp()
        self.logic = GuiApplicationLogic()
        self.gui = Gui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestSubtaskDetailsDialogCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    def test_subtask_customizer(self):
        subtask_state = SubtaskState()
        subtask_details_dialog = SubtaskDetailsDialog(self.gui.main_window.window)
        customizer = SubtaskDetailsDialogCustomizer(subtask_details_dialog, self.logic, subtask_state)
        self.assertIsInstance(customizer, SubtaskDetailsDialogCustomizer)
        self.assertEqual("0.000000 ETH", "{}".format(customizer.gui.ui.priceLabel.text()))
        subtask_state.value = 157.03 * 10 ** 16
        customizer.update_view(subtask_state)
        self.assertEqual("1.570300 ETH", "{}".format(customizer.gui.ui.priceLabel.text()))
