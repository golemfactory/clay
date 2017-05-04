import logging

from apps.rendering.gui.controller.renderercustomizer import RendererCustomizer


logger = logging.getLogger("apps.lux")


class LuxRenderDialogCustomizer(RendererCustomizer):

    def get_task_name(self):
        return "LuxRender"

    def load_data(self):
        super(LuxRenderDialogCustomizer, self).load_data()
        self._change_halts_values()

    def load_task_definition(self, definition):
        super(LuxRenderDialogCustomizer, self).load_task_definition(definition)
        self._change_halts_values()

    def _setup_connections(self):
        super(LuxRenderDialogCustomizer, self)._setup_connections()
        self.gui.ui.stopBySppRadioButton.toggled.connect(self._change_halts_state)

    def _change_halts_values(self):
        set_haltspp = self.options.haltspp > 0
        self.gui.ui.haltTimeLineEdit.setText(u"{}".format(self.options.halttime))
        self.gui.ui.haltSppLineEdit.setText(u"{}".format(self.options.haltspp))
        if self.gui.ui.stopBySppRadioButton.isChecked() and not set_haltspp:
            self.gui.ui.stopByTimeRadioButton.setChecked(True)
        if not self.gui.ui.stopBySppRadioButton.isChecked() and set_haltspp:
            self.gui.ui.stopBySppRadioButton.setChecked(True)
        self._change_halts_state()

    def _change_halts_state(self):
        spp_checked = self.gui.ui.stopBySppRadioButton.isChecked()
        self.gui.ui.haltSppLineEdit.setEnabled(spp_checked)
        self.gui.ui.haltTimeLineEdit.setEnabled(not spp_checked)

    def _change_options(self):
        if self.gui.ui.stopByTimeRadioButton.isChecked():
            self.options.haltspp = 0
            try:
                self.options.halttime = int(self.gui.ui.haltTimeLineEdit.text())
            except ValueError:
                logger.error("{} is not proper halttime value".format(self.gui.ui.haltTimeLineEdit.text()))
        else:
            self.options.halttime = 0
            try:
                self.options.haltspp = int(self.gui.ui.haltSppLineEdit.text())
            except ValueError:
                logger.error("{} in not proper haltspp value".format(self.gui.ui.haltSppLineEdit.text()))
