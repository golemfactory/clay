from PyQt4 import QtCore, QtGui
from ui_taskdialog import Ui_TaskSpecDialog

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

        QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL("accepted()"), self.accept)
        QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL("rejected()"), self.reject)

    ########################
    def getWidth( self ):
        return self.ui.widthSpinBox.value()

    ########################
    def getHeight( self ):
        return self.ui.heightSpinBox.value()

    ########################
    def getNumSamplesPerPixel( self ):
        return self.ui.samplesPerPixelSpinBox.value()

    ########################
    def getFileName( self ):
        return self.ui.imgNameInput.text()
