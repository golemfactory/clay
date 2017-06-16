from mock import Mock, patch, ANY

from apps.blender.gui.controller.blenderrenderdialogcustomizer import \
    BlenderRenderDialogCustomizer
from apps.blender.gui.view.gen.ui_BlenderWidget import Ui_BlenderWidget
from apps.blender.task.blenderrendertask import BlenderTaskTypeInfo
from apps.rendering.gui.controller.renderercustomizer import \
    FrameRendererCustomizer
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.testdirfixture import TestDirFixture
from gui.application import Gui
from gui.applicationlogic import GuiApplicationLogic
from gui.controller.mainwindowcustomizer import MainWindowCustomizer
from gui.view.appmainwindow import AppMainWindow
from gui.view.widget import TaskWidget


class TestBlenderRenderDialogCustomizer(TestDirFixture):

    def setUp(self):
        super(TestBlenderRenderDialogCustomizer, self).setUp()
        self.logic = GuiApplicationLogic()
        self.gui = Gui(Mock(), AppMainWindow)

    def tearDown(self):
        super(TestBlenderRenderDialogCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    @patch("gui.controller.customizer.QMessageBox")
    def test_blender_customizer(self, mock_messagebox):
        self.logic.customizer = MainWindowCustomizer(self.gui.main_window,
                                                     self.logic)
        self.logic.register_new_task_type(
            BlenderTaskTypeInfo(TaskWidget(Ui_BlenderWidget),
                                BlenderRenderDialogCustomizer))
        self.logic.client = Mock()
        self.logic.client.config_desc = ClientConfigDescriptor()
        self.logic.client.config_desc.use_ipv6 = False
        self.logic.client.config_desc.max_price = 0
        self.logic.client.get_config.return_value = \
            self.logic.client.config_desc
        self.logic.client.get_res_dirs.return_value = {'computing': self.path,
                                                       'received': self.path}
        self.logic.customizer.init_config()
        customizer = self.logic.customizer.new_task_dialog_customizer\
            .task_customizer

        assert isinstance(customizer, FrameRendererCustomizer)
        assert customizer.gui.ui.framesCheckBox.isChecked()
        customizer._change_options()
        assert customizer.options.frames == '1-10'
        customizer.gui.ui.framesCheckBox.setChecked(True)
        customizer.gui.ui.framesLineEdit.setText(
            u"{}".format("1;3;5-12"))
        customizer._change_options()
        assert customizer.options.frames == "1;3;5-12"
        customizer.gui.ui.framesLineEdit.setText(
            u"{}".format("Not proper frames"))
        customizer._change_options()
        assert customizer.options.frames == "1;3;5-12"
        mock_messagebox.assert_called_with(
            mock_messagebox.Critical, "Error",
            u"Wrong frame format. Frame list expected, e.g. 1;3;5-12.",
            ANY, ANY
        )
