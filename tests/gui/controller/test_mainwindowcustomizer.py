import os

from PyQt5.QtCore import QObject
from ethereum.utils import denoms
from mock import patch, MagicMock, ANY, Mock
from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from golem.testutils import TempDirFixture, TestGui

from apps.core.task.coretaskstate import TaskDesc
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

from gui.controller.mainwindowcustomizer import MainWindowCustomizer
from gui.view.tasktableelem import ItemMap


class MagicQObject(QObject):

    def __init__(self, *args):
        super(MagicQObject, self).__init__(*args)
        self.ui = MagicMock()

    @staticmethod
    def setMouseTracking(*args):
        pass


class TestMainWindowCustomizer(TestGui):

    def test_description(self):
        customizer = MainWindowCustomizer(self.gui.get_main_window(), MagicMock())
        assert isinstance(customizer, MainWindowCustomizer)
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
        customizer = MainWindowCustomizer(self.gui.get_main_window(), MagicMock())
        task1 = TaskDesc()
        task1.definition.task_id = "TASK ID 1"
        task1.status = "Finished"
        task1.definition.task_name = "TASK NAME 1"
        customizer.logic.get_task.return_value = task1
        customizer.add_task(task1)
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Id).text() == "TASK ID 1"
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Name).text() == "TASK NAME 1"
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Status).text() == "Finished"
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Cost).text() == "0.000000"
        assert customizer.gui.ui.taskTableWidget.item(0, ItemMap.Time).text() == "00:00:00"
        task2 = TaskDesc()
        task2.definition.task_id = "TASK ID 2"
        task2.status = "Waiting"
        task2.definition.task_name = "TASK NAME 2"
        customizer.logic.get_task.return_value = task2
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
        customizer.remove_task("TASK ID 2")

        customizer.logic.get_task.return_value = TaskDesc()
        customizer.show_change_task_dialog("ABC")
        customizer.change_task_dialog.close()

    def test_preview(self):
        obj = MagicQObject()
        obj.ui.outputFile = QObject()
        obj.ui.previewLabel = MagicQObject()

        customizer = MainWindowCustomizer(obj, obj)
        self.assertTrue(os.path.isfile(customizer.preview_controller.preview_path))

    def test_folderTreeView(self):
        tmp_files = self.additional_dir_content([4, [3], [2]])
        customizer = MainWindowCustomizer(self.gui.get_main_window(), MagicMock())

        customizer.gui.ui.showResourceButton.click()
        customizer.current_task_highlighted = MagicMock()
        customizer.current_task_highlighted.definition.main_scene_file = tmp_files[0]
        customizer.current_task_highlighted.definition.resources = tmp_files
        customizer.gui.ui.showResourceButton.click()

    def test_update_preview(self):
        customizer = MainWindowCustomizer(self.gui.get_main_window(), MagicMock())
        rts = TaskDesc(definition_class=RenderingTaskDefinition)
        rts.definition.output_file = "bla"
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.outputFile.text() == "bla"
        assert not customizer.gui.ui.previewsSlider.isVisible()
        assert customizer.preview_controller.last_preview_path == customizer.preview_controller.preview_path
        assert customizer.gui.ui.previewLabel.pixmap().width() == 298
        assert customizer.gui.ui.previewLabel.pixmap().height() == 200

        img = Image.new("RGB", (250, 123), "white")
        img_path = os.path.join(self.path, "image1.png")
        img.save(img_path)
        rts.task_state.extra_data = {"result_preview": img_path}
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.previewLabel.pixmap().width() == 250
        assert customizer.gui.ui.previewLabel.pixmap().height() == 123

        img = Image.new("RGB", (301, 206), "white")
        img.save(img_path)
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.previewLabel.pixmap().width() == 301
        assert customizer.gui.ui.previewLabel.pixmap().height() == 206

        rts.definition.task_type = u"Blender"
        rts.definition.options = MagicMock()
        rts.definition.options.use_frames = True
        rts.definition.options.frames = range(10)
        rts.task_state.outputs = ["result"] * 10
        rts.task_state.extra_data = {"result_preview": [img_path]}
        customizer.update_task_additional_info(rts)

    @patch("gui.controller.customizer.QMessageBox")
    def test_show_task_result(self, mock_messagebox):
        customizer = MainWindowCustomizer(self.gui.get_main_window(), MagicMock())
        td = TaskDesc()
        td.definition.task_type = "Blender"
        td.definition.options.use_frames = True
        td.definition.output_file = os.path.join(self.path, "output.png")
        td.task_state.outputs = [os.path.join(self.path, u"output0011.png"),
                                 os.path.join(self.path, u"output0014.png"),
                                 os.path.join(self.path, u"output0017.png")]
        td.definition.options.frames = [11, 14, 17]
        customizer.logic.get_task.return_value = td
        customizer.current_task_highlighted = td
        customizer.gui.ui.previewsSlider.setRange(1, 3)
        mock_messagebox.Critical = "CRITICAL"
        customizer.show_task_result("abc")
        expected_file = td.task_state.outputs[0]
        mock_messagebox.assert_called_with(mock_messagebox.Critical, "Error",
                                           expected_file + u" is not a file",
                                           ANY, ANY)
        customizer.gui.ui.previewsSlider.setValue(2)
        customizer.show_task_result("abc")
        expected_file = td.task_state.outputs[1]
        mock_messagebox.assert_called_with(mock_messagebox.Critical, "Error",
                                           expected_file + u" is not a file",
                                           ANY, ANY)
        customizer.gui.ui.previewsSlider.setValue(3)
        customizer.show_task_result("abc")
        expected_file = td.task_state.outputs[2]
        mock_messagebox.assert_called_with(mock_messagebox.Critical, "Error",
                                           expected_file + u" is not a file",
                                           ANY, ANY)

    @patch("gui.controller.mainwindowcustomizer.QMessageBox")
    def test_load_task(self, mock_messagebox):

        mock_messagebox.return_value = mock_messagebox
        customizer = MainWindowCustomizer(self.gui.get_main_window(), MagicMock())
        customizer._load_new_task_from_definition = Mock()
        task_path = os.path.join(self.path, "file.gt")

        f = Mock()
        f.read.return_value = '[{"key": "value"}]'

        with patch('__builtin__.open') as mock_open:
            mock_open.return_value = f
            customizer._load_task(task_path)

            assert mock_open.called
            assert f.close.called
            assert not mock_messagebox.exec_.called
            assert customizer._load_new_task_from_definition.called

        def _raise(*_):
            raise Exception

        f.read = _raise
        customizer._load_new_task_from_definition.called = False

        with patch('__builtin__.open') as mock_open:
            mock_open.return_value = f
            customizer._load_task(task_path)

            assert mock_open.called
            assert f.close.called
            assert mock_messagebox.exec_.called
            assert not customizer._load_new_task_from_definition.called
