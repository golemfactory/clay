from mock import Mock, patch
from PyQt4.QtCore import Qt
from PyQt4.QtTest import QTest

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.testdirfixture import TestDirFixture

from gnr.application import GNRGui

from gnr.customizers.luxrenderdialogcustomizer import LuxRenderDialogCustomizer
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.gnrstartapp import build_lux_render_info
from gnr.renderingtaskstate import RenderingTaskDefinition
from gnr.ui.appmainwindow import AppMainWindow
from gnr.ui.gen.ui_LuxWidget import Ui_LuxWidget
from gnr.ui.widget import TaskWidget


class TestLuxRenderDialogCustomizer(TestDirFixture):
    @patch("gnr.customizers.renderercustomizer.QFileDialog")
    def test_lux_customizer(self, mock_file_dialog):
        gnrgui = GNRGui(Mock(), AppMainWindow)
        logic = RenderingApplicationLogic()
        logic.register_new_renderer_type(build_lux_render_info(TaskWidget(Ui_LuxWidget), LuxRenderDialogCustomizer))
        logic.customizer = RenderingMainWindowCustomizer(gnrgui.main_window, logic)
        logic.client = Mock()
        logic.client.config_desc = ClientConfigDescriptor()
        logic.client.get_res_dirs.return_value = {'computing': self.path, 'received': self.path}
        logic.customizer.init_config()
        lux_customizer = logic.customizer.new_task_dialog_customizer.task_customizer
        assert isinstance(lux_customizer, LuxRenderDialogCustomizer)
        assert lux_customizer.get_task_name() == "LuxRender"

        logic.customizer.gui.ui.resourceFilesLabel.setText("124")
        QTest.mouseClick(logic.customizer.gui.ui.resetToDefaultButton, Qt.LeftButton)
        assert logic.customizer.gui.ui.resourceFilesLabel.text() == "0"

        definition = RenderingTaskDefinition()
        lux_customizer.get_task_specific_options(definition)
        lux_customizer.load_task_definition(definition)

        QTest.mouseClick(lux_customizer.gui.ui.chooseMainSceneFileButton, Qt.LeftButton)
        mock_file_dialog.getOpenFileName.assert_called_with(lux_customizer.gui,
                                                            "Choose main scene file",
                                                            u"",
                                                            u"Scene files (*.LXS *.lxs)")

        gnrgui.app.deleteLater()
