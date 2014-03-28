import sys
from PyQt4.QtGui import QApplication, QDialog
from ui_nodemanager import Ui_NodesManagerWidget

app = QApplication(sys.argv)
window = QDialog()
ui = Ui_NodesManagerWidget()
ui.setupUi(window)

window.show()
sys.exit(app.exec_())
