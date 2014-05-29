import datetime
from PyQt4.QtGui import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout

class SubtaskTableElem:
    ############################
    def __init__( self, nodeId, subtaskId, status ):
        self.nodeId             = nodeId
        self.nodeIdItem         = None
        self.subtaskId          = subtaskId
        self.subtaskIdItem      = None
        self.status             = status
        self.remainingTime      = 0
        self.remainingTimeItem  = None
        self.progress           = 0.0
        self.nodeIdItem         = None
        self.progressBar        = None
        self.progressBarInBoxLayoutWidget = None
        self.subtaskStatusItem  = None
        self.__buildRow()

    ############################
    def __buildRow( self ):

        self.nodeIdItem = QTableWidgetItem()
        self.nodeIdItem.setText( self.nodeId )

        self.subtaskIdItem = QTableWidgetItem()
        self.subtaskIdItem.setText( self.subtaskId )

        self.remainingTimeItem = QTableWidgetItem()

        self.subtaskStatusItem = QTableWidgetItem()

        self.progressBar = QProgressBar()
        self.progressBar.geometry().setHeight( 20 )
        self.progressBar.setProperty( "value", 50 )

        self.progressBarInBoxLayoutWidget = QWidget()
        boxLayout = QVBoxLayout()
        boxLayout.setMargin(3)
        boxLayout.addWidget( self.progressBar )
        
        self.progressBarInBoxLayoutWidget.setLayout( boxLayout )

    ############################
    def update( self, progress, status, remTime ):
        self.setProgress( progress )
        self.setRemainingTime( remTime )
        self.setStatus( status )

    ############################
    def setProgress( self, val ):
        if val >= 0.0 and val <= 1.0:
            self.progress = val
            self.progressBar.setProperty( "value", int( val * 100 ) )
        else:
            assert False, "Wrong progress setting {}".format( val )

    ############################
    def setStatus( self, status ):
        self.status = status
        self.subtaskStatusItem.setText( status )

    ############################
    def setRemainingTime( self, time ):
        self.remainingTime = time
        self.remainingTimeItem.setText( str( datetime.timedelta( seconds = time ) ) )

    ############################
    def getColumnItem( self, col ):
        if col == 0:
            return self.nodeIdItem
        if col == 1:
            return self.subtaskIdItem
        if col == 2:
            return self.remainingTimeItem
        if col == 3:
            return self.subtaskStatusItem

        assert False, "Wrong column index"