from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtTest import QTest
from mock import Mock, patch
import os

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture

from apps.lux.gui.controller.luxrenderdialogcustomizer import LuxRenderDialogCustomizer, logger
from apps.lux.gui.view.gen.ui_LuxWidget import Ui_LuxWidget
from apps.lux.task.luxrendertask import LuxRenderTaskTypeInfo
from gui.controller.mainwindowcustomizer import MainWindowCustomizer
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

from gui.application import Gui
from gui.applicationlogic import GuiApplicationLogic
from gui.view.appmainwindow import AppMainWindow
from gui.view.widget import TaskWidget


class TestLuxRenderDialogCustomizer(TestDirFixture, LogTestCase):

    def setUp(self):
        super(TestLuxRenderDialogCustomizer, self).setUp()
        self.logic = GuiApplicationLogic()
        self.gui = Gui(Mock(), AppMainWindow)

    def tearDown(self):
        super(TestLuxRenderDialogCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    @patch("apps.rendering.gui.controller.renderercustomizer.QFileDialog")
    def test_lux_customizer(self, mock_file_dialog):
        self.logic.register_new_task_type(LuxRenderTaskTypeInfo(
            TaskWidget(Ui_LuxWidget), LuxRenderDialogCustomizer))
        self.logic.customizer = MainWindowCustomizer(self.gui.main_window, self.logic)
        self.logic.dir_manager = Mock()
        self.logic.dir_manager.root_path = self.path
        self.logic.client = Mock()
        self.logic.client.config_desc = ClientConfigDescriptor()
        self.logic.client.config_desc.use_ipv6 = False
        self.logic.client.config_desc.max_price = 0
        self.logic.client.get_config.return_value = self.logic.client.config_desc
        self.logic.client.get_res_dirs.return_value = {'computing': self.path, 'received': self.path}
        self.logic.customizer.init_config()
        lux_customizer = self.logic.customizer.new_task_dialog_customizer.task_customizer
        assert isinstance(lux_customizer, LuxRenderDialogCustomizer)
        assert lux_customizer.get_task_name() == "LuxRender"

        self.logic.customizer.gui.ui.resourceFilesLabel.setText("124")
        QTest.mouseClick(self.logic.customizer.gui.ui.resetToDefaultButton, Qt.LeftButton)
        assert self.logic.customizer.gui.ui.resourceFilesLabel.text() == "0"

        definition = RenderingTaskDefinition()
        lux_customizer.get_task_specific_options(definition)
        lux_customizer.load_task_definition(definition)

        path = u"{}".format(str(lux_customizer.load_setting('main_scene_path', os.path.expanduser('~'))))
        mock_file_dialog.getOpenFileName.return_value = path, None
        QTest.mouseClick(lux_customizer.gui.ui.chooseMainSceneFileButton, Qt.LeftButton)
        mock_file_dialog.getOpenFileName.assert_called_with(lux_customizer.gui,
                                                            "Choose main scene file",
                                                            path,
                                                            u"Scene files (*.LXS *.lxs)")

        lux_customizer.gui.ui.stopByTimeRadioButton.setChecked(True)
        lux_customizer.gui.ui.haltTimeLineEdit.setText("60")
        lux_customizer._change_options()
        assert lux_customizer.options.haltspp == 0
        assert lux_customizer.options.halttime == 60
        lux_customizer.gui.ui.haltTimeLineEdit.setText("XYZ")
        with self.assertLogs(logger, level="ERROR"):
            lux_customizer._change_options()
        assert lux_customizer.options.haltspp == 0
        lux_customizer.gui.ui.stopBySppRadioButton.setChecked(True)
        lux_customizer.gui.ui.haltTimeLineEdit.setText("30")
        lux_customizer.gui.ui.haltSppLineEdit.setText("ABC")
        with self.assertLogs(logger, level="ERROR"):
            lux_customizer._change_options()
        assert lux_customizer.options.halttime == 0
        lux_customizer.gui.ui.haltSppLineEdit.setText("25")
        lux_customizer._change_options()
        assert lux_customizer.options.halttime == 0
        assert lux_customizer.options.haltspp == 25

        lux_customizer.options.haltspp = 0
        lux_customizer._change_halts_values()
        assert lux_customizer.gui.ui.stopByTimeRadioButton.isChecked()
        assert not lux_customizer.gui.ui.stopBySppRadioButton.isChecked()
        lux_customizer.options.haltspp = 24
        lux_customizer._change_halts_values()
        assert not lux_customizer.gui.ui.stopByTimeRadioButton.isChecked()
        assert lux_customizer.gui.ui.stopBySppRadioButton.isChecked()
