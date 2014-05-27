from PyQt4 import QtCore
from PyQt4.QtGui import QDialog
from ui_NewTaskDialog import Ui_NewTaskDialog

from AddTaskResourcesDialog import AddTaskResourcesDialog
from ShowTaskResourcesDialog import ShowTaskResourcesDialog

class NewTaskDialog:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_NewTaskDialog()
        self.ui.setupUi( self.window )
        QtCore.QObject.connect( self.ui.addResourceButton, QtCore.SIGNAL( "clicked()" ), self.__showAddResourcesDialog )
        QtCore.QObject.connect( self.ui.showResourceButton, QtCore.SIGNAL( "clicked()" ), self.__showShowResourcesDialog )

    ###################
    def show( self ):
        self.window.show()

    # SLOTS
    ############################
    def __showAddResourcesDialog( self ):
        self.addTaskResourceDialog = AddTaskResourcesDialog( self.window )
        self.addTaskResourceDialog.show()

    ############################
    def __showShowResourcesDialog( self ):
        self.addTaskResourceDialog = ShowTaskResourcesDialog( self.window )
        self.addTaskResourceDialog.show()
