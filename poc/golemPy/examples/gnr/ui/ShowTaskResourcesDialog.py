from PyQt4 import QtCore
from PyQt4.QtGui import QDialog, QFileSystemModel

from gen.ui_ShowTaskResourcesDialog import Ui_ShowTaskResourceDialog

class ShowTaskResourcesDialog:
    #######################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_ShowTaskResourceDialog()
        self.ui.setupUi( self.window )

        self.__setupConnections()

    ###################
    def show( self ):
        self.window.show()

    ###################
    def __setupConnections( self ):
        QtCore.QObject.connect( self.ui.folderTreeWidget
                        , QtCore.SIGNAL( "expanded ( const QModelIndex )")
                        , self.__treeViewExpanded )

        QtCore.QObject.connect( self.ui.folderTreeWidget
                        , QtCore.SIGNAL( "collapsed ( const QModelIndex )")
                        , self.__treeViewCollapsed )

    # SLOTS
    ############################
    def __treeViewExpanded( self, index ):
        self.ui.folderTreeWidget.resizeColumnToContents(0)

    ############################
    def __treeViewCollapsed( self, index ):
        self.ui.folderTreeWidget.resizeColumnToContents(0)
