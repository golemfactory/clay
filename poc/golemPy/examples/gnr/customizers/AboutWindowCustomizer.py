
from examples.gnr.ui.AboutWindow import AboutWindow
import logging

logger = logging.getLogger(__name__)

class AboutWindowCustomizer:
    #############################
    def __init__(self, gui, logic):

        assert isinstance(gui, AboutWindow)

        self.gui    = gui
        self.logic  = logic

        self.__setupConnections()
        self.__getVersion()

    #############################
    def __setupConnections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.window.close)

    #############################
    def __getVersion(self):
        name, version = self.logic.getAboutInfo()
        self.gui.ui.nameLabel.setText(name)
        self.gui.ui.versionLabel.setText(version)
