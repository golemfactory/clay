import logging
import os

from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog, QMessageBox
from gnr.ui.threedsmaxdialog import ThreeDSMaxDialog

logger = logging.getLogger(__name__)


class ThreeDSMaxDialogCustomizer:
    def __init__(self, gui, logic, new_task_dialog):
        assert isinstance(gui, ThreeDSMaxDialog)

        self.gui = gui
        self.logic = logic
        self.new_task_dialog = new_task_dialog

        self.renderer_options = new_task_dialog.renderer_options

        self.__init()
        self.__setup_connections()

    def __init(self):
        renderer = self.logic.get_renderer(u"3ds Max Renderer")
        self.gui.ui.presetLineEdit.setText(self.renderer_options.preset)
        self.gui.ui.framesCheckBox.setChecked(self.renderer_options.use_frames)
        self.gui.ui.framesLineEdit.setEnabled(self.renderer_options.use_frames)
        if self.renderer_options.use_frames:
            self.gui.ui.framesLineEdit.setText(self.__frames_to_string(self.renderer_options.frames))
        else:
            self.gui.ui.framesLineEdit.setText("")

    def __setup_connections(self):
        self.gui.ui.buttonBox.rejected.connect(self.gui.window.close)
        self.gui.ui.buttonBox.accepted.connect(lambda: self.__change_renderer_options())
        self.gui.ui.presetButton.clicked.connect(self.__choose_preset_file)

        QtCore.QObject.connect(self.gui.ui.framesCheckBox, QtCore.SIGNAL("stateChanged(int) "),
                                self.__frames_check_box_changed)

    def __change_renderer_options(self):
        self.renderer_options.preset = u"{}".format(self.gui.ui.presetLineEdit.text())
        self.renderer_options.use_frames = self.gui.ui.framesCheckBox.isChecked()
        if self.renderer_options.use_frames:
            frames = self.__string_to_frames(self.gui.ui.framesLineEdit.text())
            if not frames:
                QMessageBox().critical(None, "Error", "Wrong frame format. Frame list expected, e.g. 1,3,5-12. ")
                return
            self.renderer_options.frames = frames
        self.new_task_dialog.set_renderer_options(self.renderer_options)
        self.gui.window.close()

    def __choose_preset_file(self):
        dir_ = os.path.dirname(u"{}".format(self.gui.ui.presetLineEdit.text()))
        preset_file = u"{}".format(QFileDialog.getOpenFileName(self.gui.window, "Choose preset file", dir_, "3dsMax render preset file (*.rps)"))
        if preset_file != '':
            self.gui.ui.presetLineEdit.setText(preset_file)

    def __frames_check_box_changed(self):
        self.gui.ui.framesLineEdit.setEnabled(self.gui.ui.framesCheckBox.isChecked())
        if self.gui.ui.framesCheckBox.isChecked():
            self.gui.ui.framesLineEdit.setText(self.__frames_to_string(self.renderer_options.frames))

    def __frames_to_string(self, frames):
        s = ""
        last_frame = None
        interval = False
        for frame in sorted(frames):
            try:
                frame = int(frame)
                if frame < 0:
                    raise ValueError("Frame number must be greater or equal to 0")
                if last_frame is None:
                    s += str(frame)
                elif frame - last_frame == 1:
                    if not interval:
                        s += '-'
                        interval = True
                elif interval:
                    s += str(last_frame) + "," + str(frame)
                    interval = False
                else:
                    s += ',' + str(frame)

                last_frame = frame
            except ValueError as err:
                logger.error("Wrong frame format: {}".format(err))
                return ""

        if interval:
            s += str(last_frame)

        return s

    def __string_to_frames(self, s):
        try:
            frames = []
            after_split = s.split(",")
            for i in after_split:
                inter = i.split("-")
                if len(inter) == 1:
                    frames.append(int(inter[0]))
                elif len(inter) == 2:
                    frames += range(int(inter[0]), int(inter[1]) + 1)
                else:
                    raise ValueError("Wrong frame interval format")
            return frames
        except ValueError as err:
            logger.warning("Wrong frame format {}".format(str(err)))
            return []
