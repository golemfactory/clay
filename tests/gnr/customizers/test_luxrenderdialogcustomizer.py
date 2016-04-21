from mock import Mock

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.testdirfixture import TestDirFixture

from gnr.application import GNRGui
from gnr.customizers.luxrenderdialogcustomizer import LuxRenderDialogCustomizer
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.gnrstartapp import build_lux_render_info
from gnr.ui.appmainwindow import AppMainWindow
from gnr.ui.gen.ui_LuxWidget import Ui_LuxWidget
from gnr.ui.widget import TaskWidget


class TestLuxRenderDialogCustomizer(TestDirFixture):
    def test_lux_customizer(self):
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

        gnrgui.app.deleteLater()
