from PyQt4.QtGui import QFileDialog

from examples.gnr.ui.AddTaskResourcesDialog import AddTaskResourcesDialog
import os

class AddResourcesDialogCustomizer:
    ############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, AddTaskResourcesDialog )

        self.gui        = gui
        self.logic      = logic

        self.resources  = set()

        self.__setupConnections()

    #############################
    def __setupConnections( self ):
        self.gui.ui.okButton.clicked.connect( self.__okButtonClicked )
        self.gui.ui.chooseMainSceneFileButton.clicked.connect( self.__chooseMainSceneFileButtonClicked )

    #############################
    def __okButtonClicked( self ):
        self.resources = self.gui.ui.folderTreeView.model().exportChecked()
        self.gui.window.close()

    #############################
    def __chooseMainSceneFileButtonClicked( self ):
        sceneFileExt = self.logic.getCurrentRenderer().sceneFileExt

        outputFileTypes = " ".join( [u"*.{}".format( ext ) for ext in sceneFileExt ] )
        filter = u"Scene files ({})".format( outputFileTypes )

        dir = os.path.dirname( u"{}".format( self.gui.ui.mainSceneLabel.text() )  )

        fileName = u"{}".format( QFileDialog.getOpenFileName( self.gui.window,
            "Choose main scene file", dir, filter ) )

        if fileName != '':
            self.gui.ui.mainSceneLabel.setText( fileName )

