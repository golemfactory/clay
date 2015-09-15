import logging
from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox

from golem.environments.Environment import Environment

from examples.gnr.ui.LuxRenderDialog import LuxRenderDialog
from examples.gnr.RenderingEnvironment import LuxRenderEnvironment

logger = logging.getLogger(__name__)


class LuxRenderDialogCustomizer:
    def __init__(self, gui, logic, new_task_dialog):
        assert isinstance(gui, LuxRenderDialog)

        self.gui = gui
        self.logic = logic
        self.new_task_dialog = new_task_dialog

        self.renderer_options = new_task_dialog.renderer_options

        self.__init()
        self.__setup_connections()

    def __init(self):
        renderer = self.logic.get_renderer(u"LuxRender")
        self.gui.ui.haltTimeLineEdit.setText(u"{}".format(self.renderer_options.halttime))
        self.gui.ui.haltsppLineEdit.setText(u"{}".format(self.renderer_options.haltspp))
        if self.renderer_options.send_binaries:
            self.gui.ui.sendLuxRadioButton.toggle()
        else:
            self.gui.ui.useInstalledRadioButton.toggle()
        self.gui.ui.luxConsoleLineEdit.setEnabled(self.renderer_options.send_binaries)
        self.gui.ui.luxConsoleLineEdit.setText(u"{}".format(self.renderer_options.luxconsole))

    def __setup_connections(self):
        self.gui.ui.cancelButton.clicked.connect(self.gui.close)
        self.gui.ui.okButton.clicked.connect(lambda: self.__change_renderer_options())
        QtCore.QObject.connect(self.gui.ui.sendLuxRadioButton, QtCore.SIGNAL("toggled(bool)"), self.__send_lux_settings_changed)

    def __change_renderer_options(self):
        try:
            self.renderer_options.halttime = int(self.gui.ui.haltTimeLineEdit.text())
        except ValueError:
            logger.error("{} is not proper halttime value".format(self.gui.ui.haltTimeLineEdit.text()))
        try:
            self.renderer_options.haltspp = int(self.gui.ui.haltsppLineEdit.text())
        except ValueError:
            logger.error("{} in not proper haltspp value".format(self.gui.ui.haltsppLineEdit.text()))

        self.renderer_options.send_binaries = self.gui.ui.sendLuxRadioButton.isChecked()
        self.renderer_options.luxconsole = u"{}".format(self.gui.ui.luxConsoleLineEdit.text())

        if self.renderer_options.send_binaries:
            self.renderer_options.environment = Environment()
        else:
            self.renderer_options.environment = LuxRenderEnvironment()

        self.new_task_dialog.set_renderer_options(self.renderer_options)
        self.gui.window.close()

    def __send_lux_settings_changed(self):
        self.gui.ui.luxConsoleLineEdit.setEnabled(self.gui.ui.sendLuxRadioButton.isChecked())