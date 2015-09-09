import logging

from examples.gnr.ui.UpdateOtherGolemsDialog import UpdateOtherGolemsDialog
from examples.gnr.ui.InfoTaskDialog import InfoTaskDialog

from examples.gnr.customizers.GNRMainWindowCustomizer import GNRMainWindowCustomizer
from examples.gnr.customizers.UpdateOtherGolemsDialogCustomizer import UpdateOtherGolemsDialogCustomizer
from examples.gnr.customizers.InfoTaskDialogCustomizer import InfoTaskDialogCustomizer

logger = logging.getLogger(__name__)

class GNRAdministratorMainWindowCustomizer (GNRMainWindowCustomizer):
    #############################
    def _setup_connections(self):
        GNRMainWindowCustomizer._setup_connections(self)
        self._setup_administration_connections()

    #############################
    def _setup_administration_connections(self):
        self.gui.ui.actionSendTestTasks.triggered.connect(self._send_test_tasks)
        self.gui.ui.actionUpdateOtherGolems.triggered.connect(self._send_update_other_golems_task)
        self.gui.ui.actionSendInfoTask.triggered.connect(self._show_info_task_dialog)
        self.gui.ui.actionStartNodesManager.triggered.connect(self._start_nodes_manager)

    #############################
    def _show_info_task_dialog(self):
        self.infoTaskDialog = InfoTaskDialog(self.gui.window)
        self.infoTaskDialogCustomizer = InfoTaskDialogCustomizer(self.infoTaskDialog, self.logic)
     #   self.infoTaskDialogCustomizer.loadDefaults()
        self.infoTaskDialog.show()

    ############################
    def _send_info_task(self):
        self.logic.send_info_task()

    ############################
    def _send_test_tasks(self):
        self.logic.send_test_tasks()

    ############################
    def _send_update_other_golems_task(self):
        updateOtherGolemsDialog = UpdateOtherGolemsDialog (self.gui.window)
        updateOtherGolemsDialogCustomizer = UpdateOtherGolemsDialogCustomizer(updateOtherGolemsDialog, self.logic)
        updateOtherGolemsDialog.show()

    ############################
    def _start_nodes_manager(self):
        self.logic.start_nodes_manager_server()