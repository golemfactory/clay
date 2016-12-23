from os import path

from PyQt4.QtCore import QObject, SIGNAL
from PyQt4.QtGui import QPixmap, QPainter, QPen, QColor, QPixmapCache

from golem.task.taskstate import SubtaskStatus

from apps.core.task.gnrtaskstate import GNRTaskDefinition

from gui.controller.customizer import Customizer
from gui.guidirmanager import get_preview_file


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
        self.maincontroller = maincontroller

    def update_img(self, img):
        self.gui.ui.previewLabel.setScaledContents(False)
        self.gui.ui.previewLabel.setPixmap(img)
        QPixmapCache.clear()

    def _setup_connections(self):
        QObject.connect(self.gui.ui.previewLabel, SIGNAL("mouseReleaseEvent(int, int, QMouseEvent)"),
                        self.__pixmap_clicked)
        self.gui.ui.previewLabel.setMouseTracking(True)
        QObject.connect(self.gui.ui.previewLabel, SIGNAL("mouseMoveEvent(int, int, QMouseEvent)"),
                        self.__mouse_on_pixmap_moved)

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
            renderer = self.logic.get_task_type(definition.task_type)
            if len(task.task_state.subtask_states) > 0:
                total_tasks = task.task_state.subtask_states.values()[0].extra_data['total_tasks']
                if len(task.task_state.outputs) > 1:
                    frames = len(definition.options.frames)
                    frame_num = self.gui.ui.previewsSlider.value()
                    num = renderer.get_task_num_from_pixels(x, y, total_tasks, use_frames=True,
                                    frames=frames, frame_num=frame_num,
                                    res_x=self.maincontroller.current_task_highlighted.definition.resolution[0],
                                    res_y=self.maincontroller.current_task_highlighted.definition.resolution[1])
                else:
                    num = renderer.get_task_num_from_pixels(x, y, total_tasks,
                                    res_x=self.maincontroller.current_task_highlighted.definition.resolution[0],
                                    res_y=self.maincontroller.current_task_highlighted.definition.resolution[1])
        return num

    def __mouse_on_pixmap_moved(self, x, y, *args):
        num = self.__get_task_num_from_pixels(x, y)
        if num is not None:
            task = self.maincontroller.current_task_highlighted
            definition = task.definition
            if not isinstance(definition, GNRTaskDefinition):
                return
            renderer = self.logic.get_task_type(definition.task_type)
            subtask = self.__get_subtask(num)
            if subtask is not None:
                res_x, res_y = self.maincontroller.current_task_highlighted.definition.resolution
                if len(task.task_state.outputs) > 1:
                    frames = len(definition.options.frames)
                    frame_num = self.gui.ui.previewsSlider.value()
                    border = renderer.get_task_border(subtask.extra_data['start_task'],
                                                      subtask.extra_data['end_task'],
                                                      subtask.extra_data['total_tasks'],
                                                      res_x,
                                                      res_y,
                                                      use_frames=True,
                                                      frames=frames,
                                                      frame_num=frame_num)
                else:
                    border = renderer.get_task_border(subtask.extra_data['start_task'],
                                                      subtask.extra_data['end_task'],
                                                      subtask.extra_data['total_tasks'],
                                                      res_x,
                                                      res_y)

                if path.isfile(self.maincontroller.last_preview_path) and \
                                self.maincontroller.last_preview_path != get_preview_file():
                        self.__draw_border(border)

    def __draw_border(self, border):
        pixmap = QPixmap(self.maincontroller.last_preview_path)
        p = QPainter(pixmap)
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(3)
        p.setPen(pen)
        for (x, y) in border:
            p.drawPoint(x, y)
        p.end()
        self.update_img(pixmap)
