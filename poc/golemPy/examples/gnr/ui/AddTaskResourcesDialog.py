from PyQt4 import QtCore
from PyQt4.QtGui import QDialog

from gen.ui_AddTaskResourcesDialog import Ui_AddTaskResourcesDialog

from CheckableDirModel import CheckableDirModel

class AddTaskResourcesDialog:
    #######################
    def __init__( self, parent ):
        self.window     = QDialog( parent )
        self.ui         = Ui_AddTaskResourcesDialog()

        self.ui.setupUi( self.window )
        self.__initFolderTreeView()
        self.__setupConnections()

    ###################
    def show( self ):
        self.window.show()

    ###################
    def __initFolderTreeView( self ):

        fsModel = CheckableDirModel()
        fsModel.setRootPath("")
        fsModel.setFilter( QtCore.QDir.AllDirs | QtCore.QDir.Files | QtCore.QDir.NoDotAndDotDot )

        self.ui.folderTreeView.setModel( fsModel )
        self.ui.folderTreeView.setColumnWidth( 0, self.ui.folderTreeView.columnWidth(0) * 2 )

    ###################
    def __setupConnections( self ):
        QtCore.QObject.connect( self.ui.folderTreeView
                        , QtCore.SIGNAL( "expanded ( const QModelIndex )")
                        , self.__treeViewExpanded )

        QtCore.QObject.connect( self.ui.folderTreeView
                        , QtCore.SIGNAL( "collapsed ( const QModelIndex )")
                        , self.__treeViewCollapsed )

    # SLOTS
    ############################
    def __treeViewExpanded( self, index ):
        self.ui.folderTreeView.resizeColumnToContents(0)

    ############################
    def __treeViewCollapsed( self, index ):
        self.ui.folderTreeView.resizeColumnToContents(0)
