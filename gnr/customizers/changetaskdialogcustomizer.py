from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

from gnr.customizers.customizer import Customizer

from timehelper import set_time_spin_boxes, get_time_values

import logging

logger = logging.getLogger("gnr.gui")


class ChangeTaskDialogCustomizer(Customizer):

    def _setup_connections(self):
        self.gui.ui.saveButton.clicked.connect(self.__save_button_clicked)
        self.gui.ui.cancelButton.clicked.connect(self.__cancel_button_clicked)

    def __save_button_clicked(self):
        full_task_timeout, subtask_timeout = get_time_values(self.gui)
        self.logic.change_timeouts(u"{}".format(self.gui.ui.taskIdLabel.text()), full_task_timeout, subtask_timeout)
        self.gui.window.close()

    def load_task_definition(self, definition):
        assert isinstance(definition, RenderingTaskDefinition)

        self.gui.ui.taskIdLabel.setText(u"{}".format(definition.task_id))
        set_time_spin_boxes(self.gui, definition.full_task_timeout, definition.subtask_timeout)

    def __cancel_button_clicked(self):
        self.gui.window.close()

