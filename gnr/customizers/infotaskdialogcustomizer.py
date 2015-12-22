from gnr.ui.infotaskdialog import InfoTaskDialog
from timehelper import get_time_values

import logging

logger = logging.getLogger(__name__)


class InfoTaskDialogCustomizer:
    def __init__(self, gui, logic):

        assert isinstance(gui, InfoTaskDialog)

        self.gui    = gui
        self.logic  = logic

        self.__setup_connections()

    def __setup_connections(self):
        self.gui.ui.buttonBox.accepted.connect(self.__start_info_task)
        self.gui.ui.buttonBox.rejected.connect(self.gui.close)

    def __start_info_task(self):
        iterations = int (self.gui.ui.iterationsSpinBox.value())
        full_task_timeout, subtask_timeout, min_subtask_time = get_time_values(self.gui)
        self.logic.send_info_task(iterations, full_task_timeout, subtask_timeout)
        self.gui.close()