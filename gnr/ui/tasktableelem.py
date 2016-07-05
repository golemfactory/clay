from PyQt4.QtGui import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout


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
        box_layout.setMargin(3)
        box_layout.addWidget(self.progress_bar)

        self.progressBarInBoxLayoutWidget.setLayout(box_layout)

        self.status_item = QTableWidgetItem()
        self.status_item.setText(self.status)

    def setProgress(self, val):
        if 0.0 <= val <= 1.0:
            self.progress = val
        else:
            assert False, "Wrong progress setting {}".format(val)

    def get_column_item(self, col):
        if col == 0:
            return self.name_item
        if col == 1:
            return self.id_item
        if col == 2:
            return self.status_item

        assert False, "Wrong column index"


class ItemMap(object):
    def __init__(self):
        self.__index = {'name': 0, 'id': 1, 'status': 2, 'progress': 3}
        self.__item = {0: 'name', 1: 'id', 2: 'status', 3: 'progress'}

    def index_of(self, name):
        """
        Get index of @name item
        :param name: item name
        :return: index of item
        """
        return self.__index.get(name)

    def item_at(self, index):
        """
        Get item name for index
        :param index: index of item
        :return: item name
        """
        return self.__item.get(index)

    def count(self):
        """
        Get total number of items
        :return: number of items
        """
        return len(self.__index)


ItemMap = ItemMap()
