from PyQt5.QtWidgets import QWidget


class TaskWidget(QWidget):

    def __init__(self, widget_class):
        super(TaskWidget, self).__init__()
        self.ui = widget_class()
        self.ui.setupUi(self)
