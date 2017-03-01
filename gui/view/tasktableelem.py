import inspect
from PyQt5.QtWidgets import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout


class TaskTableElem:
    def __init__(self, id, status, task_name):
        self.id = id
        self.status = status
        self.progress = 0.0
        self.id_item = None
        self.progress_bar = None
        self.progressBarInBoxLayoutWidget = None
        self.status_item = None
        self.task_name = task_name
        self.name_item = None
        self.timer_item = None
        self.cost_item = None
        self.__build_row()

    def __build_row(self):
        self.name_item = QTableWidgetItem()
        self.name_item.setText(self.task_name)

        self.id_item = QTableWidgetItem()
        self.id_item.setText(self.id)

        self.progress_bar = QProgressBar()
        self.progress_bar.geometry().setHeight(20)
        self.progress_bar.setProperty("value", 50)

        self.progressBarInBoxLayoutWidget = QWidget()
        box_layout = QVBoxLayout()
        #box_layout.setMargin(3)
        box_layout.addWidget(self.progress_bar)

        self.progressBarInBoxLayoutWidget.setLayout(box_layout)

        self.status_item = QTableWidgetItem()
        self.status_item.setText(self.status)

        self.timer_item = QTableWidgetItem()
        self.timer_item.setText("00:00:00")

        self.cost_item = QTableWidgetItem()
        self.cost_item.setText("0.000000")

    def setProgress(self, val):
        if 0.0 <= val <= 1.0:
            self.progress = val
        else:
            raise ValueError("Wrong progress setting {}".format(val))

    def get_column_item(self, col):
        if col == 0:
            return self.name_item
        if col == 1:
            return self.id_item
        if col == 2:
            return self.status_item
        if col == 3:
            return self.timer_item
        if col == 4:
            return self.cost_item

        raise ValueError("Wrong column index {}".format(col))


class ItemMap(object):
    Name = 0
    Id = 1
    Status = 2
    Time = 3
    Cost = 4
    Progress = 5

    @staticmethod
    def count():
        """
        Return number of items in map
        :return: number of items
        """
        size = 0
        for name in dir(ItemMap):
            value = getattr(ItemMap, name)
            if not name.startswith('__') and not inspect.ismethod(value):
                if isinstance(value, int) and int(value) > size:
                    size = value
        return size + 1
