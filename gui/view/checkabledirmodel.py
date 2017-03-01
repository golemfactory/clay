import os
from PyQt5 import QtCore, QtWidgets


def are_parent_and_child(parent, child):
    while child.isValid():
        if child == parent:
            return True
        child = child.parent()
    return False


class CheckableDirModel(QtWidgets.QFileSystemModel):
    def __init__(self, parent=None):
        QtWidgets.QFileSystemModel.__init__(self, None)
        self.checks = {}
        self.start_files = {}

    def addStartFiles(self, start_files):
        self.start_files = set(start_files)

    def _isStartFile(self, index):
        if os.path.normpath(unicode(self.filePath(index))) in self.start_files:
            return True
        return False

    def _remove_from_start_files(self, index):
        self.start_files.remove(os.path.normpath(unicode(self.filePath(index))))

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:

            if self._isStartFile(index):
                self.checks[index] = QtCore.Qt.Checked

            return self.check_state(index)
        return QtWidgets.QFileSystemModel.data(self, index, role)

    def flags(self, index):
        return QtWidgets.QFileSystemModel.flags(self, index) | QtCore.Qt.ItemIsUserCheckable

    def check_state(self, index):
        while index.isValid():
            if index in self.checks:
                return self.checks[index]
            index = index.parent()
        return QtCore.Qt.Unchecked

    def setData(self, index, value, role):
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            self.layoutAboutToBeChanged.emit()
            for i, v in self.checks.items():
                if are_parent_and_child(index, i):
                    if self._isStartFile(i):
                        self._remove_from_start_files(i)
                    self.checks.pop(i)
            self.checks[index] = value
            if self._isStartFile(index):
                if value == QtCore.Qt.Unchecked:
                    self._remove_from_start_files(index)

            self.layoutChanged.emit()
            return True

        return QtWidgets.QFileSystemModel.setData(self, index, value, role)

    def add_checked_files_from_dir(self, dirFilePath, selection):
        for path, dirs, files in os.walk(unicode(dirFilePath)):
            for filename in files:
                if self.check_state(self.index(os.path.join(path, filename))) == QtCore.Qt.Checked:
                    selection.append(os.path.normpath(os.path.join(path, filename)))

    def export_checked(self):
        selection = []
        for index in self.checks.keys():
            if self.checks[index] == QtCore.Qt.Checked:
                if os.path.isfile(unicode(self.filePath(index))):
                    selection.append(os.path.normpath(unicode(self.filePath(index))))
                if os.path.isdir(unicode(self.filePath(index))):
                    self.add_checked_files_from_dir(self.filePath(index), selection)

        return set(selection)
