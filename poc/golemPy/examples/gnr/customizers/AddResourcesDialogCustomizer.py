from PyQt4.QtGui import QFileDialog

from AddTaskResourcesDialog import AddTaskResourcesDialog

class AddResourcesDialogCustomizer:
    ############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, AddTaskResourcesDialog )

        self.gui        = gui
        self.logic      = logic

        self.resources  = []

        self.__setupConnections()

    #############################
    def __setupConnections( self ):
        self.gui.ui.okButton.clicked.connect( self.__okButtonClicked )
        self.gui.ui.chooseMainSceneFileButton.clicked.connect( self.__chooseMainSceneFileButtonCliced )

    #############################
    def __okButtonClicked( self ):
        self.resources = self.gui.ui.folderTreeView.model().exportChecked()
        self.gui.window.close()

    #############################
    def __chooseMainSceneFileButtonCliced( self ):
        sceneFileExt = self.logic.getCurrentRenderer().sceneFileExt

        outputFileType = "{}".format( sceneFileExt )
        filter = "{} (*.{})".format( outputFileType, outputFileType )

        fileName = "{}".format( QFileDialog.getOpenFileName( self.gui.window,
            "Choose main scene file", "", filter ) )
        
        self.gui.ui.mainSceneLabel.setText( fileName )

