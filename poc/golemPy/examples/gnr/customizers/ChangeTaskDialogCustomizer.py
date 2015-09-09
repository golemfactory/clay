import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog

from examples.gnr.ui.ChangeTaskDialog import ChangeTaskDialog
from examples.gnr.RenderingTaskState import RenderingTaskDefinition
from TimeHelper import setTimeSpinBoxes, getTimeValues

import logging

logger = logging.getLogger(__name__)

class ChangeTaskDialogCustomizer:

    def __init__(self, gui, logic):
        assert isinstance(gui, ChangeTaskDialog)
        self.gui    = gui
        self.logic = logic

        self.__setup_connections()

    ############################
    def __setup_connections(self):
        self.gui.ui.saveButton.clicked.connect(self.__saveButtonClicked)
        self.gui.ui.cancelButton.clicked.connect(self.__cancelButtonClicked)

    ############################
    def __saveButtonClicked(self):
        full_task_timeout, subtask_timeout, min_subtask_time = getTimeValues(self.gui)
        self.logic.change_timeouts(u"{}".format(self.gui.ui.taskIdLabel.text()), full_task_timeout, subtask_timeout, min_subtask_time)
        self.gui.window.close()

    ############################
    def load_taskDefinition(self, definition):
        assert isinstance(definition, RenderingTaskDefinition)

        self.gui.ui.taskIdLabel.setText(u"{}".format(definition.task_id))
        setTimeSpinBoxes(self.gui, definition.full_task_timeout, definition.subtask_timeout, definition.min_subtask_time)

    #############################
    def __cancelButtonClicked(self):
        self.gui.window.close()

