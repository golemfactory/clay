from unittest import TestCase

from ethereum.utils import denoms
from mock import MagicMock
from PyQt4.QtCore import Qt
from PyQt4.QtTest import QTest


from gui.application import GNRGui
from gnr.customizers.gnrmainwindowcustomizer import GNRMainWindowCustomizer
from gnr.ui.appmainwindow import AppMainWindow
from gnr.ui.tasktableelem import ItemMap


class TestGNRMainWindowCustomizer(TestCase):

    def setUp(self):
        super(TestGNRMainWindowCustomizer, self).setUp()
        self.logic = MagicMock()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestGNRMainWindowCustomizer, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    def test_description(self):
        customizer = GNRMainWindowCustomizer(self.gnrgui.get_main_window(), MagicMock())
        assert isinstance(customizer, GNRMainWindowCustomizer)
        customizer.set_options(MagicMock(), "ID1", "ETH_ADDR1", "DESC1")
        assert customizer.gui.ui.descriptionTextEdit.toPlainText() == "DESC1"
        customizer.set_options(MagicMock(), "ID1", "ETH_ADDR1", "DESC2")
        assert customizer.gui.ui.descriptionTextEdit.toPlainText() == "DESC2"
        assert customizer.gui.ui.editDescriptionButton.isEnabled()
        assert not customizer.gui.ui.saveDescriptionButton.isEnabled()
        assert not customizer.gui.ui.descriptionTextEdit.isEnabled()

        QTest.mouseClick(customizer.gui.ui.editDescriptionButton, Qt.LeftButton)
        assert not customizer.gui.ui.editDescriptionButton.isEnabled()
        assert customizer.gui.ui.saveDescriptionButton.isEnabled()
        assert customizer.gui.ui.descriptionTextEdit.isEnabled()

        QTest.mouseClick(customizer.gui.ui.saveDescriptionButton, Qt.LeftButton)
        assert customizer.gui.ui.editDescriptionButton.isEnabled()
        assert not customizer.gui.ui.saveDescriptionButton.isEnabled()
        assert not customizer.gui.ui.descriptionTextEdit.isEnabled()

    def test_table(self):
        customizer = GNRMainWindowCustomizer(self.gnrgui.get_main_window(), MagicMock())
        task1 = MagicMock()
        task1.definition.task_id = "TASK ID 1"
        task1.status = "Finished"
        task1.definition.task_name = "TASK NAME 1"
        customizer.add_task(task1)
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Id).text() == "TASK ID 1"
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Name).text() == "TASK NAME 1"
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Status).text() == "Finished"
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Cost).text() == "0.000000"
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Time).text() == "00:00:00"
        task2 = MagicMock()
        task2.definition.task_id = "TASK ID 2"
        task2.status = "Waiting"
        task2.definition.task_name = "TASK NAME 2"
        customizer.add_task(task2)
        assert customizer.gui.ui.taskTableWidget.item(1, ItemMap.Id).text() == "TASK ID 2"
        assert customizer.gui.ui.taskTableWidget.item(1, ItemMap.Name).text() == "TASK NAME 2"
        assert customizer.gui.ui.taskTableWidget.item(1, ItemMap.Status).text() == "Waiting"
        assert customizer.gui.ui.taskTableWidget.item(1, ItemMap.Cost).text() == "0.000000"
        assert customizer.gui.ui.taskTableWidget.item(1, ItemMap.Time).text() == "00:00:00"
        customizer.update_time()
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Time).text() == "00:00:00"
        time_ = customizer.gui.ui.taskTableWidget.item(1, ItemMap.Time).text()
        assert time_ != "00:00:00"
        task1.task_state.status = "Computing"
        task2.task_state.progress = 0.3
        task2.task_state.status = "Paused"
        task2.task_state.progress = 1.0
        customizer.logic.get_cost_for_task_id.return_value = 2.342 * denoms.ether
        tasks = {'TASK ID 1': task1, 'TASK ID 2': task2}
        customizer.update_tasks(tasks)
        customizer.update_time()
        assert customizer.gui.ui.taskTableWidget.item(1, ItemMap.Cost).text() == "2.342000"
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Time).text() != "00:00:00"
        assert customizer.gui.ui.taskTableWidget.item(1, ItemMap.Time).text() == time_


