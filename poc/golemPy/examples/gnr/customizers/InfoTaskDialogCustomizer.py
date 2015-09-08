from examples.gnr.ui.InfoTaskDialog import InfoTaskDialog
from TimeHelper import getTimeValues

import logging

logger = logging.getLogger(__name__)

class InfoTaskDialogCustomizer:
    #############################
    def __init__(self, gui, logic):

        assert isinstance(gui, InfoTaskDialog)

        self.gui    = gui
        self.logic  = logic

        self.__setupConnections()

    #############################
    def __setupConnections(self):
        self.gui.ui.buttonBox.accepted.connect(self.__startInfoTask)
        self.gui.ui.buttonBox.rejected.connect(self.gui.close)

    def __startInfoTask(self):
        iterations = int (self.gui.ui.iterationsSpinBox.value())
        fullTaskTimeout, subtask_timeout, minSubtaskTime = getTimeValues(self.gui)
        self.logic.sendInfoTask(iterations, fullTaskTimeout, subtask_timeout)
        self.gui.close()