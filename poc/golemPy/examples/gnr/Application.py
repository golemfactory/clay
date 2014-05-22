
import sys
from PyQt4.QtGui import QApplication, QMainWindow, QWidget, QTableWidget, QTableWidgetItem, QProgressBar, QVBoxLayout, QPixmap
from ui_MainWindow import Ui_MainWindow
from GNREventHandler import GNREventHandler

class GNRGui:
    ############################
    def __init__( self ):
        self.app    = QApplication( sys.argv )
        self.window = QMainWindow()
        self.ui     = Ui_MainWindow()
        self.ui.setupUi( self.window )

        self.eventHandler = GNREventHandler( self.ui, self )
        self.ui.previewLabel.setPixmap( QPixmap( "./../examples/gnr/ui/nopreview.jpg" ) )
        self.ui.previewLabel.setFixedHeight( 200 )
        self.ui.previewLabel.setFixedWidth( 300 )

    ############################
    def execute( self ):
        self.window.show()
        sys.exit( self.app.exec_() )

    ############################
    def registerNewTask( self, id, status ):
        currentRowCount = self.ui.renderTaskTableWidget.rowCount()
        self.ui.renderTaskTableWidget.insertRow( currentRowCount )

        taskTableElem = TaskTableElem( id, status )

        for col in range( 0, 2 ): self.ui.renderTaskTableWidget.setItem( currentRowCount, col, taskTableElem.getColumnItem( col ) )

        self.ui.renderTaskTableWidget.setCellWidget( currentRowCount, 2, taskTableElem.progressBarInBoxLayoutWidget )

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

