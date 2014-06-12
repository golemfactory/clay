from PyQt4.QtGui import QDialog
from PyQt4 import QtCore
from gen.ui_TestingTaskProgressDialog import Ui_testingTaskProgressDialog

class TestingTaskProgressDialog:
    ###################
    def __init__( self, parent, taskTester ):
        self.taskTester     = taskTester
        self.window         = QDialog( parent )
        self.ui             = Ui_testingTaskProgressDialog()
        self.ui.setupUi( self.window )

    ###################
    def setProgress( self, val ):
        if val:
            self.ui.progressBar.setProperty( "value", int( val * 100 ) )
        else:
            self.ui.progressBar.setProperty( "value", 0 )

    ###################
    def show( self ):
        self.window.show()
        QtCore.QTimer.singleShot( 500, self.__updateProgress )

    def close( self ):
        self.window.close()

    ####################
    def __updateProgress( self ):
        self.setProgress( self.taskTester.getProgress() )
        QtCore.QTimer.singleShot( 500, self.__updateProgress )