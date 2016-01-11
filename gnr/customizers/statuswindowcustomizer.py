from gnr.customizers.customizer import Customizer

import logging

logger = logging.getLogger(__name__)


class StatusWindowCustomizer(Customizer):

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.__ok_button_clicked)

    def __ok_button_clicked(self):
        self.gui.window.close()

    def get_status(self):
        self.gui.ui.statusTextBrowser.setText(self.logic.get_status())
