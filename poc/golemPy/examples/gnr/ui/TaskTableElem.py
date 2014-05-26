from PyQt4.QtGui import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout

class TaskTableElem:
    ############################
    def __init__( self, id, status ):
        self.id                 = id
        self.status             = status
        self.progress           = 0.0
        self.idItem             = None
        self.progressBar        = None
        self.progressBarInBoxLayoutWidget = None
        self.statusItem         = None
        self.__buildRow()

    ############################
    def __buildRow( self ):

        self.idItem = QTableWidgetItem()
        self.idItem.setText( self.id )


        self.progressBar = QProgressBar()
        self.progressBar.geometry().setHeight( 20 )
        self.progressBar.setProperty( "value", 50 )

        self.progressBarInBoxLayoutWidget = QWidget()
        boxLayout = QVBoxLayout()
        boxLayout.setMargin(3)
        boxLayout.addWidget( self.progressBar )
        
        self.progressBarInBoxLayoutWidget.setLayout( boxLayout )

        self.statusItem = QTableWidgetItem()
        self.statusItem.setText( self.status )

    ############################
    def setProgress( self, val ):
        if val >= 0.0 and val <= 1.0:
            self.progress = val
        else:
            assert False, "Wrong progress setting {}".format( val )

    def getColumnItem( self, col ):
        if col == 0:
            return self.idItem
        if col == 1:
            return self.statusItem

        assert False, "Wrong column index"