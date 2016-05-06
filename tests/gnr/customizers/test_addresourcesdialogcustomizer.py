from mock import Mock

from PyQt4.QtCore import Qt
from PyQt4.QtTest import QTest

from gnr.application import GNRGui
from gnr.customizers.addresourcesdialogcustomizer import AddResourcesDialogCustomizer
from gnr.gnrstartapp import register_rendering_task_types
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow
from gnr.ui.dialog import AddTaskResourcesDialog
from golem.tools.testdirfixture import TestDirFixture


class TestAddResourcesDialogCustomizer(TestDirFixture):
    def test_add_resource(self):
        gnrgui = GNRGui(Mock(), AppMainWindow)
        gnrgui.show = Mock()
        gnrgui.main_window.show = Mock()
        logic = RenderingApplicationLogic()
        logic.client = Mock()
        logic.customizer = Mock()
        register_rendering_task_types(logic)
        ard = AddTaskResourcesDialog(gnrgui.main_window.window)
        ardc = AddResourcesDialogCustomizer(ard, logic)
        assert isinstance(ardc, AddResourcesDialogCustomizer)
        assert len(ardc.resources) == 0
        QTest.mouseClick(ardc.gui.ui.okButton, Qt.LeftButton)
        logic.customizer.gui.ui.resourceFilesLabel.setText.assert_called_with("0")
        files = self.additional_dir_content([5, [2], [4]])
        model = ardc.gui.ui.folderTreeView.model()
        for f in files:
            model.setData(model.index(f), Qt.Checked, Qt.CheckStateRole)
        QTest.mouseClick(ardc.gui.ui.okButton, Qt.LeftButton)
        logic.customizer.gui.ui.resourceFilesLabel.setText.assert_called_with("11")
        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()
