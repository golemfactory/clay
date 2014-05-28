from PyQt4 import QtCore
from PyQt4.QtGui import QDialog, QFileSystemModel

from ui_ShowTaskResourcesDialog import Ui_ShowTaskResourceDialog

class ShowTaskResourcesDialog:
    #######################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_ShowTaskResourceDialog()
        self.ui.setupUi( self.window )

        self.__initFolderTreeView()
        self.__setupConnections()

    ###################
    def show( self ):
        self.window.show()

    ###################
    def __initFolderTreeView( self ):

        pass
        #fsModel = QFileSystemModel()
        #fsModel.setRootPath("")
        #fsModel.setFilter( QtCore.QDir.AllDirs | QtCore.QDir.Files | QtCore.QDir.NoDotAndDotDot )

        #self.ui.folderTreeView.setModel( fsModel )

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
