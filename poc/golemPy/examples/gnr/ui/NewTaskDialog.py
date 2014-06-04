from PyQt4 import QtCore
from PyQt4.QtGui import QDialog
from gen.ui_NewTaskDialog import Ui_NewTaskDialog

from AddTaskResourcesDialog import AddTaskResourcesDialog
from ShowTaskResourcesDialog import ShowTaskResourcesDialog

class NewTaskDialog:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_NewTaskDialog()
        self.ui.setupUi( self.window )

    ###################
    def show( self ):
        self.window.show()
