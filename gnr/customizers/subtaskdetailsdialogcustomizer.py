import datetime


class SubtaskDetailsDialogCustomizer:
    #
    def __init__(self, gui, logic, subtask_state):
        self.gui = gui
        self.logic = logic
        self.subtask_state = subtask_state
        self.__setup_connections()
        self.update_view(self.subtask_state)

    #
    def update_view(self, subtask_state):
        self.subtask_state = subtask_state
        self.__update_data()

    #
    def __update_data(self):
        self.gui.ui.subtaskIdLabel.setText(self.subtask_state.subtask_id)
        self.gui.ui.nodeNameLabel.setText(self.subtask_state.computer.node_name)
        self.gui.ui.nodeIpAddressLabel.setText(self.subtask_state.computer.ip_address)
        self.gui.ui.statusLabel.setText(self.subtask_state.subtask_status)
        self.gui.ui.performanceLabel.setText("{}".format(self.subtask_state.computer.performance))
        self.gui.ui.subtaskDefinitionTextEdit.setPlainText(self.subtask_state.subtask_definition)

    #
    def __setup_connections(self):
        self.gui.ui.closeButton.clicked.connect(self.gui.window.close)
