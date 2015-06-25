import logging

from examples.gnr.ui.UpdateOtherGolemsDialog import UpdateOtherGolemsDialog
from examples.gnr.ui.InfoTaskDialog import InfoTaskDialog

from examples.gnr.customizers.GNRMainWindowCustomizer import GNRMainWindowCustomizer
from examples.gnr.customizers.UpdateOtherGolemsDialogCustomizer import UpdateOtherGolemsDialogCustomizer
from examples.gnr.customizers.InfoTaskDialogCustomizer import InfoTaskDialogCustomizer

logger = logging.getLogger(__name__)

class GNRAdministratorMainWindowCustomizer (GNRMainWindowCustomizer):
    #############################
    def _setupConnections(self):
        GNRMainWindowCustomizer._setupConnections(self)
        self._setupAdministrationConnections()

    #############################
    def _setupAdministrationConnections(self):
        self.gui.ui.actionSendTestTasks.triggered.connect(self._sendTestTasks)
        self.gui.ui.actionUpdateOtherGolems.triggered.connect(self._sendUpdateOtherGolemsTask)
        self.gui.ui.actionSendInfoTask.triggered.connect(self._showInfoTaskDialog)
        self.gui.ui.actionStartNodesManager.triggered.connect(self._startNodesManager)

    #############################
    def _showInfoTaskDialog(self):
        self.infoTaskDialog = InfoTaskDialog(self.gui.window)
        self.infoTaskDialogCustomizer = InfoTaskDialogCustomizer(self.infoTaskDialog, self.logic)
     #   self.infoTaskDialogCustomizer.loadDefaults()
        self.infoTaskDialog.show()

    ############################
    def _sendInfoTask(self):
        self.logic.sendInfoTask()

    ############################
    def _sendTestTasks(self):
        self.logic.sendTestTasks()

    ############################
    def _sendUpdateOtherGolemsTask(self):
        updateOtherGolemsDialog = UpdateOtherGolemsDialog (self.gui.window)
        updateOtherGolemsDialogCustomizer = UpdateOtherGolemsDialogCustomizer(updateOtherGolemsDialog, self.logic)
        updateOtherGolemsDialog.show()

    ############################
    def _startNodesManager(self):
        self.logic.startNodesManagerServer()