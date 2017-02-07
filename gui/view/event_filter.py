from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal


class EventFilter(QObject):
    signal = pyqtSignal('QMouseEvent')

    def __init__(self, widget, event):
        super(QObject, self).__init__(widget)
        self.widget = widget
        self.event = event

    def eventFilter(self, obj, event):
        if obj == self.widget:
            if event.type() == self.event:
                if obj.rect().contains(event.pos()):
                    self.signal.emit(event)
                    return True
        return False


def mouse_click(widget):
    filter = EventFilter(widget, QEvent.MouseButtonRelease)
    widget.installEventFilter(filter)
    return filter.signal


def mouse_move(widget):
    filter = EventFilter(widget, QEvent.MouseMove)
    widget.installEventFilter(filter)
    return filter.signal


