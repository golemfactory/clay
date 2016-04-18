import logging

from renderercustomizer import RendererCustomizer


logger = logging.getLogger(__name__)


class LuxRenderDialogCustomizer(RendererCustomizer):

    def get_task_name(self):
        return "LuxRender"

    def load_data(self):
        super(LuxRenderDialogCustomizer, self).load_data()
        self.gui.ui.haltTimeLineEdit.setText(u"{}".format(self.renderer_options.halttime))
        self.gui.ui.haltsppLineEdit.setText(u"{}".format(self.renderer_options.haltspp))

    def _change_renderer_options(self):
        try:
            self.renderer_options.halttime = int(self.gui.ui.haltTimeLineEdit.text())
        except ValueError:
            logger.error("{} is not proper halttime value".format(self.gui.ui.haltTimeLineEdit.text()))
        try:
            self.renderer_options.haltspp = int(self.gui.ui.haltsppLineEdit.text())
        except ValueError:
            logger.error("{} in not proper haltspp value".format(self.gui.ui.haltsppLineEdit.text()))
