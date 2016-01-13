
from gnr.ui.aboutwindow import AboutWindow
import logging

logger = logging.getLogger(__name__)


class AboutWindowCustomizer:
    def __init__(self, gui, logic):

        assert isinstance(gui, AboutWindow)

        self.gui = gui
        self.logic = logic

        self.__setup_connections()
        self.__get_version()

    def __setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.window.close)

    def __get_version(self):
        name, version = self.logic.get_about_info()
        self.gui.ui.nameLabel.setText(name)
        self.gui.ui.versionLabel.setText(version)
