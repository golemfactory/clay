
from gnr.ui.statuswindow import StatusWindow

import logging

logger = logging.getLogger(__name__)


class StatusWindowCustomizer:
    def __init__(self, gui, logic):

        assert isinstance(gui, StatusWindow)

        self.gui = gui
        self.logic = logic

        self.__setup_connections()

    def __setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.__ok_button_clicked)

    def __ok_button_clicked(self):
        self.gui.window.close()

    def get_status(self):
        self.gui.ui.statusTextBrowser.setText(self.logic.get_status())
