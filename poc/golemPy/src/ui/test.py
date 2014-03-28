import sys
from PyQt4.QtGui import QApplication, QDialog
from ui_nodemanager import Ui_NodesManagerWidget
from manager_customization import UICustomizationService

app = QApplication(sys.argv)
window = QDialog()
ui = Ui_NodesManagerWidget()

ui.setupUi(window)

ucs = UICustomizationService( ui )
ucs.addProgressBar( 0, 2 )
ucs.addProgressBar( 0, 3 )


window.show()
sys.exit(app.exec_())
