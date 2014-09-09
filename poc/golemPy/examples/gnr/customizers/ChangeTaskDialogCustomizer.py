import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog

from examples.gnr.ui.ChangeTaskDialog import ChangeTaskDialog
from examples.gnr.TaskState import TaskDefinition
from TimeHelper import setTimeSpinBoxes, getTimeValues

import logging

logger = logging.getLogger(__name__)

class ChangeTaskDialogCustomizer:

    def __init__( self, gui, logic ):
        assert isinstance( gui, ChangeTaskDialog )
        self.gui    = gui
        self.logic = logic

        self.__setupConnections()

    ############################
    def __setupConnections( self ):
        self.gui.ui.saveButton.clicked.connect( self.__saveButtonClicked )
        self.gui.ui.cancelButton.clicked.connect( self.__cancelButtonClicked )

    ############################
    def __saveButtonClicked( self ):
        fullTaskTimeout, subtaskTimeout, minSubtaskTime = getTimeValues( self.gui )
        self.logic.changeTimeouts( u"{}".format( self.gui.ui.taskIdLabel.text() ), fullTaskTimeout, subtaskTimeout, minSubtaskTime )
        self.gui.window.close()

    ############################
    def loadTaskDefinition( self, definition ):
        assert isinstance( definition, TaskDefinition )

        self.gui.ui.taskIdLabel.setText( u"{}".format( definition.id ) )
        setTimeSpinBoxes( self.gui, definition.fullTaskTimeout, definition.subtaskTimeout, definition.minSubtaskTime )

    #############################
    def __cancelButtonClicked( self ):
        self.gui.window.close()

