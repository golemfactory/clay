import datetime
from PyQt5.QtWidgets import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout


class SubtaskTableElem:
    def __init__(self, node_name, subtask_id, status):
        self.node_name = node_name
        self.node_name_item = None
        self.subtask_id = subtask_id
        self.subtask_id_item = None
        self.status = status
        self.remaining_time = 0
        self.remaining_timeItem = None
        self.progress = 0.0
        self.node_name_item = None
        self.progress_bar = None
        self.progressBarInBoxLayoutWidget = None
        self.subtask_status_item = None
        self.__build_row()

    def __build_row(self):

        self.node_name_item = QTableWidgetItem()
        self.node_name_item.setText(self.node_name)

        self.subtask_id_item = QTableWidgetItem()
        self.subtask_id_item.setText(self.subtask_id)

        self.remaining_timeItem = QTableWidgetItem()

        self.subtask_status_item = QTableWidgetItem()

        self.progress_bar = QProgressBar()
        self.progress_bar.geometry().setHeight(20)
        self.progress_bar.setProperty("value", 50)

        self.progressBarInBoxLayoutWidget = QWidget()
        boxLayout = QVBoxLayout()
        #boxLayout.setMargin(3)
        boxLayout.addWidget(self.progress_bar)

        self.progressBarInBoxLayoutWidget.setLayout(boxLayout)

    def update(self, progress, status, remTime):
        self.setProgress(progress)
        self.setRemainingTime(remTime)
        self.setStatus(status)

    def setProgress(self, val):
        if 0.0 <= val <= 1.0:
            self.progress = val
            self.progress_bar.setProperty("value", int(val * 100))
        else:
            raise ValueError("Wrong progress setting {}".format(val))

    def setStatus(self, status):
        self.status = status
        self.subtask_status_item.setText(status)

    def setRemainingTime(self, time):
        self.remaining_time = time
        self.remaining_timeItem.setText(str(datetime.timedelta(seconds=time)))

    def get_column_item(self, col):
        if col == 0:
            return self.node_name_item
        if col == 1:
            return self.subtask_id_item
        if col == 2:
            return self.remaining_timeItem
        if col == 3:
            return self.subtask_status_item

        raise ValueError("Wrong column index")
