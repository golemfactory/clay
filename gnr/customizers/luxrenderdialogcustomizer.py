import logging
from PyQt4 import QtCore

from renderercustomizer import RendererCustomizer
from golem.environments.environment import Environment

from gnr.docker_environments import LuxRenderEnvironment

logger = logging.getLogger(__name__)


class LuxRenderDialogCustomizer(RendererCustomizer):

    def load_data(self):
        renderer = self.logic.get_renderer(u"LuxRender")
        self.gui.ui.haltTimeLineEdit.setText(u"{}".format(self.renderer_options.halttime))
        self.gui.ui.haltsppLineEdit.setText(u"{}".format(self.renderer_options.haltspp))

    def _setup_connections(self):
        self.gui.ui.cancelButton.clicked.connect(self.gui.close)
        self.gui.ui.okButton.clicked.connect(lambda: self.__change_renderer_options())

    def __change_renderer_options(self):
        try:
            self.renderer_options.halttime = int(self.gui.ui.haltTimeLineEdit.text())
        except ValueError:
            logger.error("{} is not proper halttime value".format(self.gui.ui.haltTimeLineEdit.text()))
        try:
            self.renderer_options.haltspp = int(self.gui.ui.haltsppLineEdit.text())
        except ValueError:
            logger.error("{} in not proper haltspp value".format(self.gui.ui.haltsppLineEdit.text()))

        self.renderer_options.environment = LuxRenderEnvironment()

        self.new_task_dialog.set_renderer_options(self.renderer_options)
        self.gui.window.close()
