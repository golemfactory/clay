from PyQt4.QtGui import *
from PyQt4.QtCore import *

class   ClickableQLabel(QLabel):

    def __init(self, parent):
        QLabel.__init__(self, parent)

    def mouseReleaseEvent(self, ev):
        self.emit(SIGNAL('mouseReleaseEvent( int, int, QMouseEvent)'), ev.pos().x(), ev.pos().y(), ev )