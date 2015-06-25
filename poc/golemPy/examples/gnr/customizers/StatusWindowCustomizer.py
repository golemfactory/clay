
from examples.gnr.ui.StatusWindow import StatusWindow

import logging

logger = logging.getLogger(__name__)

class StatusWindowCustomizer:
    #############################
    def __init__(self, gui, logic):

        assert isinstance(gui, StatusWindow)

        self.gui    = gui
        self.logic  = logic

        self.__setupConnections()

    #############################
    def __setupConnections(self):
        self.gui.ui.okButton.clicked.connect(self.__okButtonClicked)

    #############################
    def __okButtonClicked(self):
        self.gui.window.close()


    def getStatus(self):
        self.gui.ui.statusTextBrowser.setText(self.logic.getStatus())
