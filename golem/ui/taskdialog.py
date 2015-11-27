from PyQt4 import QtCore, QtGui
from gen.ui_taskdialog import Ui_TaskSpecDialog

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class TaskSpecDialog(QtGui.QDialog):
    
    ########################
    def __init__(self, parent):
        QtGui.QDialog.__init__(self, parent)

        # Set up the user interface from Designer.
        self.ui = Ui_TaskSpecDialog()
        self.ui.setupUi(self)

        self.recreateFileName()

        QtCore.QObject.connect(self.ui.widthSpinBox, QtCore.SIGNAL("valueChanged(int)"), self.recreateFileName)
        QtCore.QObject.connect(self.ui.heightSpinBox, QtCore.SIGNAL("valueChanged(int)"), self.recreateFileName)
        QtCore.QObject.connect(self.ui.samplesPerPixelSpinBox, QtCore.SIGNAL("valueChanged(int)"), self.recreateFileName)

        QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL("accepted()"), self.accept)
        QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL("rejected()"), self.reject)

    ########################
    def recreateFileName(self):
        w = self.getWidth()
        h = self.getHeight()
        spp = self.getNumSamplesPerPixel()

        fn = "default_{}_{}_{}".format(w, h, spp)

        self.ui.imgNameInput.setText(fn)

    ########################
    def getWidth(self):
        return self.ui.widthSpinBox.value()

    ########################
    def getHeight(self):
        return self.ui.heightSpinBox.value()

    ########################
    def getNumSamplesPerPixel(self):
        return self.ui.samplesPerPixelSpinBox.value()

    ########################
    def getFileName(self):
        return self.ui.imgNameInput.text()
