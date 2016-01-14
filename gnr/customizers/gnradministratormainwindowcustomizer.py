import logging
from gnr.ui.dialog import InfoTaskDialog, UpdateOtherGolemsDialog
from gnr.customizers.gnrmainwindowcustomizer import GNRMainWindowCustomizer
from gnr.customizers.updateothergolemsdialogcustomizer import UpdateOtherGolemsDialogCustomizer
from gnr.customizers.infotaskdialogcustomizer import InfoTaskDialogCustomizer

logger = logging.getLogger(__name__)


class GNRAdministratorMainWindowCustomizer(GNRMainWindowCustomizer):
    def _setup_connections(self):
        GNRMainWindowCustomizer._setup_connections(self)
        self._setup_administration_connections()

    def _setup_administration_connections(self):
        self.gui.ui.actionSendTestTasks.triggered.connect(self._send_test_tasks)
        self.gui.ui.actionUpdateOtherGolems.triggered.connect(self._send_update_other_golems_task)
        self.gui.ui.actionSendInfoTask.triggered.connect(self._show_info_task_dialog)
        self.gui.ui.actionStartNodesManager.triggered.connect(self._start_nodes_manager)

    def _show_info_task_dialog(self):
        self.info_task_dialog = InfoTaskDialog(self.gui.window)
        self.info_task_dialog_customizer = InfoTaskDialogCustomizer(self.info_task_dialog, self.logic)
        #   self.info_task_dialog_customizer.loadDefaults()
        self.info_task_dialog.show()

    def _send_info_task(self):
        self.logic.send_info_task()

    def _send_test_tasks(self):
        self.logic.send_test_tasks()

    def _send_update_other_golems_task(self):
        update_other_golems_dialog = UpdateOtherGolemsDialog(self.gui.window)
        update_other_golems_dialog_customizer = UpdateOtherGolemsDialogCustomizer(update_other_golems_dialog,
                                                                                  self.logic)
        update_other_golems_dialog.show()

    def _start_nodes_manager(self):
        self.logic.start_nodes_manager_server()
