from PyQt4.QtGui import QAction

class SubtaskContextMenuCustomizer:
    ##########################
    def __init__( self, ui, logic, subtaskId ):
        self.ui         = ui
        self.logic      = logic
        self.subtaskId  = subtaskId

        self.__buildContextMenu()

    ##########################
    def __buildContextMenu( self ):
        action = QAction( "Restart", self.ui )
        action.setEnabled( True )
        action.triggered.connect( self.__restartSubtask )
        self.ui.addAction( action )
        return action

    ##########################
    def __restartSubtask( self ):
        self.logic.restartSubtask( self.subtaskId )
