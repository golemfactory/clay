from examples.gnr.ui.UpdateOtherGolemsDialog import UpdateOtherGolemsDialog

from PyQt4.QtGui import QFileDialog, QMessageBox

import logging
import os

logger = logging.getLogger(__name__)

class UpdateOtherGolemsDialogCustomizer:
    #############################
    def __init__(self, gui, logic):

        assert isinstance(gui, UpdateOtherGolemsDialog)

        self.gui    = gui
        self.logic  = logic
        self.golemDir = ""

        self.__setup_connections()

    #############################
    def __setup_connections(self):
        self.gui.ui.folderButton.clicked.connect(self.__chooseSrcFolder)
        self.gui.ui.buttonBox.accepted.connect(lambda: self.__updateOtherGolems())
        self.gui.ui.buttonBox.rejected.connect(self.gui.window.close)

    def __chooseSrcFolder(self):
        dir = u"{}".format(QFileDialog.getExistingDirectory(self.gui.window, "Choose golem source directory",
                                                 "",
                                                 QFileDialog.ShowDirsOnly))
        if dir is not None:
            self.golemDir = dir
            self.gui.ui.srcDirLineEdit.setText("{}".format(self.golemDir))


    def __updateOtherGolems(self):
        if not os.path.isdir(self.golemDir):
            QMessageBox().critical(None, "Error", "{} is not a dir".format(self.golemDir))
        else:
            reply = QMessageBox.question(self.gui.window, 'Golem Message',
                "Are you sure you want to update other Golems?", QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.logic.updateOtherGolems(self.golemDir)
                self.gui.window.close()