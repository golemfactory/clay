from mock import Mock

from golem.tools.testdirfixture import TestDirFixture

from gnr.application import GNRGui
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow


class TestRenderingApplicationLogic(TestDirFixture):
    def test_change_verification_options(self):
        logic = RenderingApplicationLogic()
        gnrgui = GNRGui(Mock(), AppMainWindow)
        logic.client = Mock()
        logic.client.datadir = self.path
        logic.customizer = RenderingMainWindowCustomizer(gnrgui.main_window, logic)
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
