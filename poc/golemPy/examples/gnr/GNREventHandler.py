
from PyQt4 import QtCore

class GNREventHandler:
    ##########################
    def __init__( self, ui, app ):
        self.ui     = ui
        self.app    = app
        self.__setupConnections()


