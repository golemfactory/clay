import os
from PyQt4 import QtGui, QtCore

def are_parent_and_child(parent, child):
    while child.isValid():
        if child == parent:
            return True
        child = child.parent()
    return False


class CheckableDirModel(QtGui.QFileSystemModel):
    def __init__(self, parent=None):
        QtGui.QFileSystemModel.__init__(self, None)
        self.checks = {}

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            return self.checkState(index)
        return QtGui.QFileSystemModel.data(self, index, role)

    def flags(self, index):
        return QtGui.QFileSystemModel.flags(self, index) | QtCore.Qt.ItemIsUserCheckable

    def checkState(self, index):
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
                    self.checks.pop(i)
            self.checks[index] = value
            self.layoutChanged.emit()
            return True 

        return QtGui.QFileSystemModel.setData(self, index, value, role)

    def exportChecked(self ):
        selection = []
        for index in self.checks.keys():
            if self.checks[index] == QtCore.Qt.Checked:
                for path, dirs, files in os.walk(unicode(self.filePath(index))):
                    for filename in files:
                        if self.checkState(self.index(os.path.join(path, filename))) == QtCore.Qt.Checked:
                            try:
                                selection.append(os.path.join(path, filename))
                            except:
                                pass
        return list( set( selection ) )