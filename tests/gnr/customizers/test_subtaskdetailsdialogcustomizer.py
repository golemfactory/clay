from unittest import TestCase

from golem.task.taskstate import SubtaskState

from gui.application import GNRGui
from gnr.customizers.subtaskdetailsdialogcustomizer import SubtaskDetailsDialogCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow
from gnr.ui.dialog import SubtaskDetailsDialog


class TestSubtaskDetailsDialogCustomizer(TestCase):

    def setUp(self):
        super(TestSubtaskDetailsDialogCustomizer, self).setUp()
        self.logic = RenderingApplicationLogic()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestSubtaskDetailsDialogCustomizer, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    def test_subtask_customizer(self):
        subtask_state = SubtaskState()
        subtask_details_dialog = SubtaskDetailsDialog(self.gnrgui.main_window.window)
        customizer = SubtaskDetailsDialogCustomizer(subtask_details_dialog, self.logic, subtask_state)
        assert isinstance(customizer, SubtaskDetailsDialogCustomizer)
        assert "0.000000 ETH" == "{}".format(customizer.gui.ui.priceLabel.text())
        subtask_state.value = 157.03 * 10 ** 16
        customizer.update_view(subtask_state)
        assert "1.570300 ETH" == "{}".format(customizer.gui.ui.priceLabel.text())
