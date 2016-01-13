from PyQt4.QtGui import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout


class TaskTableElem:
    def __init__(self, id, status):
        self.id = id
        self.status = status
        self.progress = 0.0
        self.id_item = None
        self.progress_bar = None
        self.progressBarInBoxLayoutWidget = None
        self.status_item = None
        self.__build_row()

    def __build_row(self):

        self.id_item = QTableWidgetItem()
        self.id_item.setText(self.id)

        self.progress_bar = QProgressBar()
        self.progress_bar.geometry().setHeight(20)
        self.progress_bar.setProperty("value", 50)

        self.progressBarInBoxLayoutWidget = QWidget()
        boxLayout = QVBoxLayout()
        boxLayout.setMargin(3)
        boxLayout.addWidget(self.progress_bar)

        self.progressBarInBoxLayoutWidget.setLayout(boxLayout)

        self.status_item = QTableWidgetItem()
        self.status_item.setText(self.status)

    def setProgress(self, val):
        if 0.0 <= val <= 1.0:
            self.progress = val
        else:
            assert False, "Wrong progress setting {}".format(val)

    def get_column_item(self, col):
        if col == 0:
            return self.id_item
        if col == 1:
            return self.status_item

        assert False, "Wrong column index"
