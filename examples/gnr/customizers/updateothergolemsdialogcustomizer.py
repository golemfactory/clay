from examples.gnr.ui.updateothergolemsdialog import UpdateOtherGolemsDialog

from PyQt4.QtGui import QFileDialog, QMessageBox

import logging
import os

logger = logging.getLogger(__name__)


class UpdateOtherGolemsDialogCustomizer:

    def __init__(self, gui, logic):

        assert isinstance(gui, UpdateOtherGolemsDialog)

        self.gui    = gui
        self.logic  = logic
        self.golem_dir = ""

        self.__setup_connections()

    def __setup_connections(self):
        self.gui.ui.folderButton.clicked.connect(self.__choose_src_folder)
        self.gui.ui.buttonBox.accepted.connect(lambda: self.__update_other_golems())
        self.gui.ui.buttonBox.rejected.connect(self.gui.window.close)

    def __choose_src_folder(self):
        dir_ = u"{}".format(QFileDialog.getExistingDirectory(self.gui.window, "Choose golem source directory",
                                                 "",
                                                 QFileDialog.ShowDirsOnly))
        if dir_ is not None:
            self.golem_dir = dir_
            self.gui.ui.srcDirLineEdit.setText("{}".format(self.golem_dir))

    def __update_other_golems(self):
        if not os.path.isdir(self.golem_dir):
            QMessageBox().critical(None, "Error", "{} is not a dir".format(self.golem_dir))
        else:
            reply = QMessageBox.question(self.gui.window, 'Golem Message',
                "Are you sure you want to update other Golems?", QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.logic.update_other_golems(self.golem_dir)
                self.gui.window.close()