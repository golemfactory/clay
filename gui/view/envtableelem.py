from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtCore import Qt


class EnvTableElem:
    colItem = ["id_item", "status_item", "accept_tasks_item", "short_description_item"]

    def __init__(self, id, status, short_description, acceptTask):
        self.id = id
        self.status = status
        self.short_description = short_description
        self.accept_tasks = acceptTask
        self.id_item = None
        self.status_item = None
        self.short_description_item = None
        self.accept_tasks_item = None

        self.__build_row()
        self.column_item_translation = {"id_item": self.__get_id_item,
                                        "status_item": self.__get_status_item,
                                        "accept_tasks_item": self.__get_cccept_tasks_item,
                                        "short_description_item": self.__get_short_description_item}

    def get_column_item(self, col):
        if col < len(EnvTableElem.colItem):
            if EnvTableElem.colItem[col] in self.column_item_translation:
                return self.column_item_translation[EnvTableElem.colItem[col]]()

        raise ValueError("Wrong column index")

    def change_accept_task(self, state):
        self.accept_tasks = state

    def __build_row(self):

        self.id_item = QTableWidgetItem()
        self.id_item.setText(self.id)

        self.status_item = QTableWidgetItem()
        self.status_item.setText(self.status)

        self.short_description_item = QTableWidgetItem()
        self.short_description_item.setText(self.short_description)

        self.accept_tasks_item = QTableWidgetItem()
        self.accept_tasks_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        if self.accept_tasks:
            self.accept_tasks_item.setCheckState(Qt.Checked)
        else:
            self.accept_tasks_item.setCheckState(Qt.Unchecked)

    def __get_id_item(self):
        return self.id_item

    def __get_status_item(self):
        return self.status_item

    def __get_cccept_tasks_item(self):
        return self.accept_tasks_item

    def __get_short_description_item(self):
        return self.short_description_item
