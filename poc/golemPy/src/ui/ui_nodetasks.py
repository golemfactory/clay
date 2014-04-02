# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'nodetasks.ui'
#
# Created: Wed Apr 02 16:28:42 2014
#      by: PyQt4 UI code generator 4.10.3
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_NodeTasksWidget(object):
    def setupUi(self, NodeTasksWidget):
        NodeTasksWidget.setObjectName(_fromUtf8("NodeTasksWidget"))
        NodeTasksWidget.resize(690, 501)
        self.gridLayout = QtGui.QGridLayout(NodeTasksWidget)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.tableLocalTasks = QtGui.QTableWidget(NodeTasksWidget)
        self.tableLocalTasks.setObjectName(_fromUtf8("tableLocalTasks"))
        self.tableLocalTasks.setColumnCount(2)
        self.tableLocalTasks.setRowCount(0)
        item = QtGui.QTableWidgetItem()
        self.tableLocalTasks.setHorizontalHeaderItem(0, item)
        item = QtGui.QTableWidgetItem()
        self.tableLocalTasks.setHorizontalHeaderItem(1, item)
        self.gridLayout.addWidget(self.tableLocalTasks, 1, 0, 1, 1)
        self.tableRemoteTasks = QtGui.QTableWidget(NodeTasksWidget)
        self.tableRemoteTasks.setObjectName(_fromUtf8("tableRemoteTasks"))
        self.tableRemoteTasks.setColumnCount(2)
        self.tableRemoteTasks.setRowCount(0)
        item = QtGui.QTableWidgetItem()
        self.tableRemoteTasks.setHorizontalHeaderItem(0, item)
        item = QtGui.QTableWidgetItem()
        self.tableRemoteTasks.setHorizontalHeaderItem(1, item)
        self.gridLayout.addWidget(self.tableRemoteTasks, 1, 1, 1, 1)
        self.nodeUidLabel = QtGui.QLabel(NodeTasksWidget)
        self.nodeUidLabel.setObjectName(_fromUtf8("nodeUidLabel"))
        self.gridLayout.addWidget(self.nodeUidLabel, 0, 0, 1, 2)

        self.retranslateUi(NodeTasksWidget)
        QtCore.QMetaObject.connectSlotsByName(NodeTasksWidget)

    def retranslateUi(self, NodeTasksWidget):
        NodeTasksWidget.setWindowTitle(_translate("NodeTasksWidget", "Form", None))
        item = self.tableLocalTasks.horizontalHeaderItem(0)
        item.setText(_translate("NodeTasksWidget", "Task ID", None))
        item = self.tableLocalTasks.horizontalHeaderItem(1)
        item.setText(_translate("NodeTasksWidget", "Local Tasks", None))
        item = self.tableRemoteTasks.horizontalHeaderItem(0)
        item.setText(_translate("NodeTasksWidget", "Task ID", None))
        item = self.tableRemoteTasks.horizontalHeaderItem(1)
        item.setText(_translate("NodeTasksWidget", "Remote Tasks", None))
        self.nodeUidLabel.setText(_translate("NodeTasksWidget", "TextLabel", None))

