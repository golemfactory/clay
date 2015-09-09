import logging
import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog

from copy import deepcopy

from examples.gnr.ui.PbrtTaskDialog import PbrtTaskDialog
from examples.gnr.task.GNRTask import GNROptions
from VerificationParamsHelper import readAdvanceVerificationParams, setVerificationWidgetsState, loadVerificationParams, \
                                        verificationRandomChanged

logger = logging.getLogger(__name__)

class PbrtTaskDialogCustomizer:
    #############################
    def __init__(self, gui, logic, newTaskDialog):

        assert isinstance(gui, PbrtTaskDialog)

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog
        self.options = deepcopy(newTaskDialog.options)

        self.__init()
        self.__setup_connections()

    #############################
    def __init(self):
        self.__setRendererParameters()
        self.__setOutputParameters()
        self.__setVerificationParameters()

    #############################
    def __setRendererParameters(self) :
        self.gui.ui.pixelFilterComboBox.clear()
        self.gui.ui.pixelFilterComboBox.addItems(self.options.filters)
        pixel_filterItem = self.gui.ui.pixelFilterComboBox.findText(self.options.pixel_filter)
        if pixel_filterItem >= 0:
            self.gui.ui.pixelFilterComboBox.setCurrentIndex(pixel_filterItem)

        self.gui.ui.pathTracerComboBox.clear()
        self.gui.ui.pathTracerComboBox.addItems(self.options.path_tracers)

        algItem = self.gui.ui.pathTracerComboBox.findText(self.options.algorithm_type)

        if algItem >= 0:
            self.gui.ui.pathTracerComboBox.setCurrentIndex(algItem)

        self.gui.ui.samplesPerPixelSpinBox.setValue(self.options.samples_per_pixel_count)
        #self.gui.ui.pbrtPathLineEdit.setText(self.options.pbrt_path)

        self.gui.ui.mainSceneLineEdit.setText(self.options.main_scene_file)

    #############################
    def __setOutputParameters(self):
        self.gui.ui.outputResXSpinBox.setValue (self.options.resolution[0])
        self.gui.ui.outputResYSpinBox.setValue (self.options.resolution[1])

        self.gui.ui.outputFormatsComboBox.clear()
        self.gui.ui.outputFormatsComboBox.addItems(self.options.output_formats)
        for idx, output_format in enumerate(self.options.output_formats):
            if output_format == self.options.output_format:
                self.gui.ui.outputFormatsComboBox.setCurrentIndex(idx)

        self.gui.ui.outputFileLineEdit.setText(self.options.output_file)

    #############################
    def __setVerificationParameters(self):
        loadVerificationParams(self.gui, self.options)

    ############################
    def __setVerificationWidgetsState(self, state):
        setVerificationWidgetsState(self.gui, state)

    #############################
    def __setup_connections(self):
        self.gui.ui.cancelButton.clicked.connect(self.gui.window.close)
        self.gui.ui.okButton.clicked.connect(lambda: self.__changeRendererOptions())
        self.gui.ui.chooseOutputFileButton.clicked.connect(self.__chooseOutputFileButtonClicked)
        self.gui.ui.mainSceneButton.clicked.connect(self.__chooseMainSceneFileButtonClicked)
        self.gui.ui.pbrtPathButton.clicked.connect(self.__choosePbrtPath)
        QtCore.QObject.connect(self.gui.ui.outputResXSpinBox, QtCore.SIGNAL("valueChanged(const QString)"), self.__res_x_changed)
        QtCore.QObject.connect(self.gui.ui.outputResYSpinBox, QtCore.SIGNAL("valueChanged(const QString)"), self.__res_y_changed)
        QtCore.QObject.connect(self.gui.ui.verificationRandomRadioButton, QtCore.SIGNAL("toggled(bool)"), self.__verification_random_changed)
        QtCore.QObject.connect(self.gui.ui.advanceVerificationCheckBox, QtCore.SIGNAL("stateChanged(int)"), self.__advanceVerificationChanged)

    #############################
    def __changeRendererOptions(self):
        self.__read_renderer_params()
        self.__readOutputParams()
        self.__readVerificationParams()
        self.newTaskDialog.setOptions(self.options)
        self.gui.window.close()

    #############################
    def __read_renderer_params(self):
        self.options.pixel_filter = u"{}".format(self.gui.ui.pixelFilterComboBox.itemText(self.gui.ui.pixelFilterComboBox.currentIndex()))
        self.options.samples_per_pixel_count = self.gui.ui.samplesPerPixelSpinBox.value()
        self.options.algorithm_type = u"{}".format(self.gui.ui.pathTracerComboBox.itemText(self.gui.ui.pathTracerComboBox.currentIndex()))
        self.options.main_scene_file = os.path.normpath(u"{}".format(self.gui.ui.mainSceneLineEdit.text()))
        self.options.pbrt_path = u"{}".format(self.gui.ui.pbrtPathLineEdit.text())

    #############################
    def __readOutputParams(self):
        self.options.resolution        = [ self.gui.ui.outputResXSpinBox.value(), self.gui.ui.outputResYSpinBox.value() ]
        self.options.output_file        = u"{}".format(self.gui.ui.outputFileLineEdit.text())
        self.options.output_format      = u"{}".format(self.gui.ui.outputFormatsComboBox.itemText(self.gui.ui.outputFormatsComboBox.currentIndex()))

    #############################
    def __readVerificationParams(self):
        return readAdvanceVerificationParams(self.gui, self.options)

    #############################
    def __chooseMainSceneFileButtonClicked(self):
        outputFileTypes = " ".join([u"*.{}".format(ext) for ext in self.options.scene_file_ext ])
        filter = u"Scene files ({})".format(outputFileTypes)


        dir = os.path.dirname(u"{}".format(self.gui.ui.mainSceneLineEdit.text()) )

        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
            "Choose main scene file", dir, filter))

        if file_name != '':
            self.gui.ui.mainSceneLineEdit.setText(file_name)


    #############################
    def __chooseOutputFileButtonClicked(self):
        outputFileType = u"{}".format(self.gui.ui.outputFormatsComboBox.currentText())
        filter = u"{} (*.{})".format(outputFileType, outputFileType)

        dir = os.path.dirname(u"{}".format(self.gui.ui.outputFileLineEdit.text()) )

        file_name = u"{}".format(QFileDialog.getSaveFileName(self.gui.window,
            "Choose output file", dir, filter))

        if file_name != '':
            self.gui.ui.outputFileLineEdit.setText(file_name)

    #############################
    def __choosePbrtPath(self):
        dir = os.path.dirname(u"{}".format(self.gui.ui.pbrtPathLineEdit.text()))
        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window, "Choose pbrt file", dir, ""))
        if file_name != '':
            self.gui.ui.pbrtPathLineEdit.setText(file_name)

    #############################
    def __verification_random_changed(self):
        verificationRandomChanged(self.gui)

    #############################
    def __res_x_changed(self):
        self.gui.ui.verificationSizeXSpinBox.setMaximum(self.gui.ui.outputResXSpinBox.value())

    #############################
    def __res_y_changed(self):
        self.gui.ui.verificationSizeYSpinBox.setMaximum(self.gui.ui.outputResYSpinBox.value())

    #############################
    def __advanceVerificationChanged(self):
        state = self.gui.ui.advanceVerificationCheckBox.isChecked()
        self.__setVerificationWidgetsState(state)