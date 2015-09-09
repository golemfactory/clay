import logging
import os

from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog, QMessageBox
from examples.gnr.ui.ThreeDSMaxDialog import ThreeDSMaxDialog

logger = logging.getLogger(__name__)

class ThreeDSMaxDialogCustomizer:
    #############################
    def __init__(self, gui, logic, newTaskDialog):
        assert isinstance(gui, ThreeDSMaxDialog)

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog

        self.rendererOptions = newTaskDialog.rendererOptions

        self.__init()
        self.__setup_connections()

    #############################
    def __init(self):
        renderer = self.logic.getRenderer(u"3ds Max Renderer")
        self.gui.ui.presetLineEdit.setText(self.rendererOptions.preset)
        self.gui.ui.framesCheckBox.setChecked(self.rendererOptions.useFrames)
        self.gui.ui.framesLineEdit.setEnabled(self.rendererOptions.useFrames)
        if self.rendererOptions.useFrames:
            self.gui.ui.framesLineEdit.setText(self.__framesToString(self.rendererOptions.frames))
        else:
            self.gui.ui.framesLineEdit.setText("")


    #############################
    def __setup_connections(self):
        self.gui.ui.buttonBox.rejected.connect(self.gui.window.close)
        self.gui.ui.buttonBox.accepted.connect(lambda: self.__changeRendererOptions())
        self.gui.ui.presetButton.clicked.connect(self.__choosePresetFile)

        QtCore.QObject.connect(self.gui.ui.framesCheckBox, QtCore.SIGNAL("stateChanged(int) "),
                                self.__framesCheckBoxChanged)

    #############################
    def __changeRendererOptions(self):
        self.rendererOptions.preset = u"{}".format(self.gui.ui.presetLineEdit.text())
        self.rendererOptions.useFrames = self.gui.ui.framesCheckBox.isChecked()
        if self.rendererOptions.useFrames:
            frames = self.__stringToFrames(self.gui.ui.framesLineEdit.text())
            if not frames:
                QMessageBox().critical(None, "Error", "Wrong frame format. Frame list expected, e.g. 1,3,5-12. ")
                return
            self.rendererOptions.frames = frames
        self.newTaskDialog.setRendererOptions(self.rendererOptions)
        self.gui.window.close()

    #############################
    def __choosePresetFile(self):
        dir = os.path.dirname(u"{}".format(self.gui.ui.presetLineEdit.text()))
        presetFile = u"{}".format(QFileDialog.getOpenFileName(self.gui.window, "Choose preset file", dir, "3dsMax render preset file (*.rps)"))
        if presetFile != '':
            self.gui.ui.presetLineEdit.setText (presetFile)

    #############################
    def __framesCheckBoxChanged(self):
        self.gui.ui.framesLineEdit.setEnabled(self.gui.ui.framesCheckBox.isChecked())
        if self.gui.ui.framesCheckBox.isChecked():
            self.gui.ui.framesLineEdit.setText(self.__framesToString(self.rendererOptions.frames))

    #############################
    def __framesToString(self, frames):
        s = ""
        lastFrame = None
        interval = False
        for frame in sorted(frames):
            try:
                frame = int (frame)
                if frame < 0:
                    raise

                if lastFrame == None:
                    s += str(frame)
                elif frame - lastFrame == 1:
                    if not interval:
                        s += '-'
                        interval = True
                elif interval:
                    s += str(lastFrame) + "," + str(frame)
                    interval = False
                else:
                    s += ',' + str(frame)

                lastFrame = frame

            except:
                logger.error("Wrong frame format")
                return ""

        if interval:
            s += str(lastFrame)

        return s

    #############################
    def __stringToFrames(self, s):
        try:
            frames = []
            splitted = s.split(",")
            for i in splitted:
                inter = i.split("-")
                if len (inter) == 1:
                    frames.append(int (inter[0]))
                elif len(inter) == 2:
                    frames += range(int(inter[0]), int(inter[1]) + 1)
                else:
                    raise
            return frames
        except:
            return []
