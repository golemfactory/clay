from mock import Mock

from gnr.application import GNRGui
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.renderingtaskstate import RenderingTaskState
from gnr.ui.appmainwindow import AppMainWindow
from golem.tools.testdirfixture import TestDirFixture


class TestRenderingApplicationLogic(TestDirFixture):

    def setUp(self):
        super(TestRenderingApplicationLogic, self).setUp()
        self.logic = RenderingApplicationLogic()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestRenderingApplicationLogic, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    def test_change_verification_options(self):
        logic = self.logic
        logic.client = Mock()
        logic.client.datadir = self.path
        logic.customizer = RenderingMainWindowCustomizer(self.gnrgui.main_window, logic)
        prev_y = logic.customizer.gui.ui.verificationSizeYSpinBox.maximum()
        logic.change_verification_option(size_x_max=914)
        assert logic.customizer.gui.ui.verificationSizeXSpinBox.maximum() == 914
        assert logic.customizer.gui.ui.verificationSizeYSpinBox.maximum() == prev_y
        logic.change_verification_option(size_y_max=123)
        assert logic.customizer.gui.ui.verificationSizeXSpinBox.maximum() == 914
        assert logic.customizer.gui.ui.verificationSizeYSpinBox.maximum() == 123
        logic.change_verification_option(size_y_max=3190, size_x_max=134)
        assert logic.customizer.gui.ui.verificationSizeXSpinBox.maximum() == 134
        assert logic.customizer.gui.ui.verificationSizeYSpinBox.maximum() == 3190

    def test_error_messages(self):
        logic = self.logic
        rts = RenderingTaskState()
        logic._validate_task_state(rts)