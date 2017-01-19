from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from mock import Mock

from golem.tools.testdirfixture import TestDirFixture

from apps.core.gui.controller.addresourcesdialogcustomizer import AddResourcesDialogCustomizer

from gui.application import Gui
from gui.applicationlogic import GuiApplicationLogic
from gui.startapp import register_task_types
from gui.view.appmainwindow import AppMainWindow
from gui.view.dialog import AddTaskResourcesDialog


class TestAddResourcesDialogCustomizer(TestDirFixture):

    def setUp(self):
        super(TestAddResourcesDialogCustomizer, self).setUp()
        self.logic = GuiApplicationLogic()
        self.gui = Gui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestAddResourcesDialogCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    def test_add_resource(self):
        self.gui.show = Mock()
        self.gui.main_window.show = Mock()
        self.logic.client = Mock()
        self.logic.customizer = Mock()
        register_task_types(self.logic)
        ard = AddTaskResourcesDialog(self.gui.main_window.window)
        ardc = AddResourcesDialogCustomizer(ard, self.logic)
        assert isinstance(ardc, AddResourcesDialogCustomizer)
        assert len(ardc.resources) == 0
        QTest.mouseClick(ardc.gui.ui.okButton, Qt.LeftButton)
        self.logic.customizer.gui.ui.resourceFilesLabel.setText.assert_called_with("0")
        files = self.additional_dir_content([5, [2], [4]])
        model = ardc.gui.ui.folderTreeView.model()
        for f in files:
            model.setData(model.index(f), Qt.Checked, Qt.CheckStateRole)
        QTest.mouseClick(ardc.gui.ui.okButton, Qt.LeftButton)
        self.logic.customizer.gui.ui.resourceFilesLabel.setText.assert_called_with("11")
