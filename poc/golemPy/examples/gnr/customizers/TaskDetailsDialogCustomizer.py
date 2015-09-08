import datetime

from PyQt4 import QtCore
from PyQt4.QtGui import QMenu

from golem.task.TaskState import TaskState, ComputerState
from examples.gnr.RenderingTaskState import RenderingTaskState
from SubtaskContextMenuCustomizer import SubtaskContextMenuCustomizer

from examples.gnr.ui.SubtaskTableEntry import SubtaskTableElem

class TaskDetailsDialogCustomizer:
    ###########################
    def __init__(self, gui, logic, gnrTaskState):
    #    assert isinstance(gnrTaskState, RenderingTaskState)
        self.gui            = gui
        self.logic          = logic
        self.gnrTaskState   = gnrTaskState

        self.subtaskTableElements = {}

        self.__setupConnections()

        self.updateView(self.gnrTaskState.taskState)

    ###########################
    def updateView(self, taskState):
        self.gnrTaskState.taskState = taskState
        self.__updateData()

    ###########################
    def __updateData(self):
        self.gui.ui.totalTaskProgressBar.setProperty("value", int(self.gnrTaskState.taskState.progress * 100))
        self.gui.ui.estimatedRemainingTimeLabel.setText(str(datetime.timedelta(seconds = self.gnrTaskState.taskState.remainingTime)))
        self.gui.ui.elapsedTimeLabel.setText(str(datetime.timedelta(seconds = self.gnrTaskState.taskState.elapsedTime)))

        for k in self.gnrTaskState.taskState.subtaskStates:
            if k not in self.subtaskTableElements:
                ss = self.gnrTaskState.taskState.subtaskStates[ k ]
                self.__addNode(ss.computer.node_id, ss.subtask_id, ss.subtaskStatus)

        for k, elem in self.subtaskTableElements.items():
            if elem.subtask_id in self.gnrTaskState.taskState.subtaskStates:
                ss = self.gnrTaskState.taskState.subtaskStates[ elem.subtask_id ]
                elem.update(ss.subtaskProgress, ss.subtaskStatus, ss.subtaskRemTime)
            else:
                del self.subtaskTableElements[ k ]

    ###########################
    def __setupConnections(self):
        QtCore.QObject.connect(self.gui.ui.nodesTableWidget, QtCore.SIGNAL("cellClicked(int, int)"), self.__nodesTabelRowClicked)
        QtCore.QObject.connect(self.gui.ui.nodesTableWidget, QtCore.SIGNAL("itemSelectionChanged()"), self.__nodesTabelRowSelected)
        self.gui.ui.nodesTableWidget.customContextMenuRequested.connect(self.__contextMenuRequested)
        self.gui.ui.closeButton.clicked.connect(self.__closeButtonClicked)

    # ###########################
    # def __initializeData(self):
    #     self.gui.ui.totalTaskProgressBar.setProperty("value", int(self.gnrTaskState.taskState.progress * 100))
    #     self.gui.ui.estimatedRemainingTimeLabel.setText(str(datetime.timedelta(seconds = self.gnrTaskState.taskState.remainingTime)))
    #     self.gui.ui.elapsedTimeLabel.setText(str(datetime.timedelta(seconds = self.gnrTaskState.taskState.elapsedTime)))
    #     for k in self.gnrTaskState.taskState.subtaskStates:
    #         if k not in self.subtaskTableElements:
    #             ss = self.gnrTaskState.taskState.subtaskStates[ k ]
    #             self.__addNode(ss.computer.node_id, ss.subtask_id, ss.subtaskStatus)

    ###########################
    def __updateNodeAdditionalInfo(self, node_id, subtask_id):
        if subtask_id in self.gnrTaskState.taskState.subtaskStates:
            ss = self.gnrTaskState.taskState.subtaskStates[ subtask_id ]
            comp = ss.computer


            assert isinstance(comp, ComputerState)

            self.gui.ui.nodeIdLabel.setText(node_id)
            self.gui.ui.nodeIpAddressLabel.setText(comp.ipAddress)
            self.gui.ui.performanceLabel.setText("{} rays per sec".format(comp.performance))
            self.gui.ui.subtaskDefinitionTextEdit.setPlainText(ss.subtaskDefinition)

    ############################
    def __addNode(self, node_id, subtask_id, status):
        currentRowCount = self.gui.ui.nodesTableWidget.rowCount()
        self.gui.ui.nodesTableWidget.insertRow(currentRowCount)

        subtaskTableElem = SubtaskTableElem(node_id, subtask_id, status)

        for col in range(0, 4): self.gui.ui.nodesTableWidget.setItem(currentRowCount, col, subtaskTableElem.getColumnItem(col))

        self.gui.ui.nodesTableWidget.setCellWidget(currentRowCount, 4, subtaskTableElem.progressBarInBoxLayoutWidget)

        self.subtaskTableElements[ subtask_id ] = subtaskTableElem

        subtaskTableElem.update(0.0, "", 0.0)

        self.__updateNodeAdditionalInfo(node_id, subtask_id)

    # SLOTS
    ###########################
    def __nodesTabelRowClicked(self, r, c):

        node_id = "{}".format(self.gui.ui.nodesTableWidget.item(r, 0).text())
        subtask_id = "{}".format(self.gui.ui.nodesTableWidget.item(r, 1).text())
        self.__updateNodeAdditionalInfo(node_id, subtask_id)

    ###########################
    def __nodesTabelRowSelected (self):
        if self.gui.ui.nodesTableWidget.selectedItems():
            row = self.gui.ui.nodesTableWidget.selectedItems()[0].row()
            node_id = "{}".format(self.gui.ui.nodesTableWidget.item(row, 0).text())
            subtask_id = "{}".format(self.gui.ui.nodesTableWidget.item(row, 1).text())
            self.__updateNodeAdditionalInfo(node_id, subtask_id)

    ###########################
    def __closeButtonClicked(self):
        self.gui.window.close()

    def __contextMenuRequested(self, p):
        if self.gui.ui.nodesTableWidget.itemAt(p) is None:
            return
        row = self.gui.ui.nodesTableWidget.itemAt(p).row()
        idItem = self.gui.ui.nodesTableWidget.item(row, 1)
        subtask_id = "{}".format(idItem.text())
        idItem = self.gui.ui.nodesTableWidget.item(row, 3)
        subtaskStatus = "{}".format(idItem.text())
        menu = QMenu()
        self.subtaskContextMenuCustomizer = SubtaskContextMenuCustomizer(menu, self.logic, subtask_id, subtaskStatus)
        menu.popup(self.gui.ui.nodesTableWidget.viewport().mapToGlobal(p))
        menu.exec_()
