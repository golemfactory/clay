from logging import getLogger
from os import path

from PyQt4.QtCore import QObject, SIGNAL
from PyQt4.QtGui import QPixmap, QPainter, QPen, QColor, QPixmapCache

from golem.task.taskstate import SubtaskStatus

from apps.core.task.gnrtaskstate import GNRTaskDefinition

from gui.controller.customizer import Customizer
from gui.guidirmanager import get_preview_file


logger = getLogger("gui")


def subtasks_priority(sub):
    priority = {
        SubtaskStatus.restarted: 6,
        SubtaskStatus.failure: 5,
        SubtaskStatus.resent: 4,
        SubtaskStatus.finished: 3,
        SubtaskStatus.starting: 2,
        SubtaskStatus.waiting: 1}

    return priority[sub.subtask_status]


class PreviewController(Customizer):
    def __init__(self, gui, logic, maincontroller):
        super(PreviewController, self).__init__(gui, logic)
        self.preview_path = get_preview_file()
        self.last_preview_path = self.preview_path
        self.slider_previews = {}
        self.maincontroller = maincontroller

        self.gui.ui.previewsSlider.setVisible(False)

    def update_img(self, img):
        self.gui.ui.previewLabel.setScaledContents(False)
        self.gui.ui.previewLabel.setPixmap(img)
        QPixmapCache.clear()

    def set_preview(self, task_desc):
        if task_desc.has_multiple_outputs():
            self._set_slider_preview(task_desc)
        else:
            self._set_preview(task_desc)

    def _setup_connections(self):
        QObject.connect(self.gui.ui.previewLabel, SIGNAL("mouseReleaseEvent(int, int, QMouseEvent)"),
                        self.__pixmap_clicked)
        self.gui.ui.previewLabel.setMouseTracking(True)
        QObject.connect(self.gui.ui.previewLabel, SIGNAL("mouseMoveEvent(int, int, QMouseEvent)"),
                        self.__mouse_on_pixmap_moved)
        self.gui.ui.previewsSlider.valueChanged.connect(self._update_slider_preview)

    def _set_preview(self, task_desc):
        self.gui.ui.outputFile.setText(u"{}".format(task_desc.definition.output_file))
        self.__update_output_file_color()
        self.gui.ui.previewsSlider.setVisible(False)
        if "result_preview" in task_desc.task_state.extra_data and \
                path.exists(path.abspath(task_desc.task_state.extra_data["result_preview"])):
            file_path = path.abspath(task_desc.task_state.extra_data["result_preview"])
            self.update_img(QPixmap(file_path))
            self.last_preview_path = file_path
        else:
            self.preview_path = get_preview_file()
            self.update_img(QPixmap(self.preview_path))
            self.last_preview_path = self.preview_path

    def _set_slider_preview(self, task_desc):
        if "result_preview" in task_desc.task_state.extra_data:
            self.slider_previews = task_desc.task_state.extra_data["result_preview"]
        self.gui.ui.previewsSlider.setVisible(True)
        self.gui.ui.previewsSlider.setRange(1, len(task_desc.task_state.outputs))
        self.gui.ui.previewsSlider.setSingleStep(1)
        self.gui.ui.previewsSlider.setPageStep(1)
        self._update_slider_preview()

    def _update_slider_preview(self):
        num = self.gui.ui.previewsSlider.value() - 1
        self._set_output_file(num)
        self.__update_output_file_color()
        if len(self.slider_previews) > num:
            if self.slider_previews[num]:
                if path.exists(self.slider_previews[num]):
                    self.update_img(QPixmap(self.slider_previews[num]))
                    self.last_preview_path = self.slider_previews[num]
                    return

        self.update_img(QPixmap(self.preview_path))
        self.last_preview_path = self.preview_path

    def _set_output_file(self, num):
        if self.maincontroller.current_task_highlighted.has_multiple_outputs(num + 1):
            self.gui.ui.outputFile.setText(self.maincontroller.current_task_highlighted.task_state.outputs[num])
        else:
            logger.warning("Output file name for {} output result hasn't been set yet".format(num))
            self.gui.ui.outputFile.setText(u"")

    def __pixmap_clicked(self, x, y, *args):
        num = self.__get_task_num_from_pixels(x, y)
        if num is None:
            return

        subtask = self.__get_subtask(num)
        if subtask is not None:
            self.maincontroller.show_subtask_details_dialog(subtask)

    def __get_subtask(self, num):
        subtask = None
        task = self.logic.get_task(self.maincontroller.current_task_highlighted.definition.task_id)
        subtasks = [sub for sub in task.task_state.subtask_states.values() if
                    sub.extra_data['start_task'] <= num <= sub.extra_data['end_task']]
        if len(subtasks) > 0:
            subtask = min(subtasks, key=lambda x: subtasks_priority(x))
        return subtask

    def __get_task_num_from_pixels(self, x, y):
        num = None

        t = self.maincontroller.current_task_highlighted
        if t is None or not isinstance(t.definition, GNRTaskDefinition):
            return

        if t.definition.task_type:
            definition = t.definition

            scaled_size = self.gui.ui.previewLabel.pixmap().size()

            scaled_x = scaled_size.width()
            scaled_y = scaled_size.height()

            margin_left = (300. - scaled_x) / 2.
            margin_right = 300. - margin_left

            margin_top = (200. - scaled_y) / 2.
            margin_bottom = 200. - margin_top

            if x <= margin_left or x >= margin_right or y <= margin_top or y >= margin_bottom:
                return

            x = (x - margin_left)
            y = (y - margin_top) + 1
            task_id = definition.task_id
            task = self.logic.get_task(task_id)
            task_type = self.logic.get_task_type(definition.task_type)
            total_subtasks = task.task_state.total_subtasks
            if len(task.task_state.subtask_states) > 0:
                if task.has_multiple_outputs():
                    num = task_type.get_task_num_from_pixels(x, y, task.definition, total_subtasks,
                                                             self.gui.ui.previewsSlider.value())
                else:
                    num = task_type.get_task_num_from_pixels(x, y, task.definition, total_subtasks)
        return num

    def __mouse_on_pixmap_moved(self, x, y, *args):
        num = self.__get_task_num_from_pixels(x, y)
        if num is not None:
            task = self.maincontroller.current_task_highlighted
            definition = task.definition
            if not isinstance(definition, GNRTaskDefinition):
                return
            task_type = self.logic.get_task_type(definition.task_type)
            subtask = self.__get_subtask(num)
            if subtask is not None:
                if task.has_multiple_outputs():
                    border = task_type.get_task_border(subtask, task.definition, task.task_state.total_subtasks,
                                                       self.gui.ui.previewsSlider.value())

                else:
                    border = task_type.get_task_border(subtask, task.definition, task.task_state.total_subtasks)

                if path.isfile(self.last_preview_path) and self.last_preview_path != get_preview_file():
                        self.__draw_border(border)

    def __draw_border(self, border):
        pixmap = QPixmap(self.last_preview_path)
        p = QPainter(pixmap)
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(3)
        p.setPen(pen)
        for (x, y) in border:
            p.drawPoint(x, y)
        p.end()
        self.update_img(pixmap)

    def __update_output_file_color(self):
        if path.isfile(self.gui.ui.outputFile.text()):
            self.gui.ui.outputFile.setStyleSheet('color: blue')
        else:
            self.gui.ui.outputFile.setStyleSheet('color: black')