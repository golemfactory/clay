from __future__ import division

from ethereum.utils import denoms

from customizer import Customizer


class SubtaskDetailsDialogCustomizer(Customizer):

    def __init__(self, gui, logic, subtask_state):
        self.subtask_state = subtask_state
        Customizer.__init__(self, gui, logic)
        self.update_view(self.subtask_state)

    def update_view(self, subtask_state):
        self.subtask_state = subtask_state
        self.__update_data()

    def _setup_connections(self):
        self.gui.ui.closeButton.clicked.connect(self.gui.window.close)
        self.gui.ui.showResultButton.clicked.connect(lambda: self.__show_result_clicked())

    def __update_data(self):
        self.gui.ui.subtaskIdLabel.setText(self.subtask_state.subtask_id)
        self.gui.ui.nodeNameLabel.setText(self.subtask_state.computer.node_name)
        self.gui.ui.nodeIpAddressLabel.setText(self.subtask_state.computer.ip_address)
        self.gui.ui.statusLabel.setText(self.subtask_state.subtask_status)
        self.gui.ui.performanceLabel.setText("{}".format(self.subtask_state.computer.performance))
        self.gui.ui.subtaskDefinitionTextEdit.setPlainText(self.subtask_state.subtask_definition)
        self.gui.ui.subtaskOutputLogTextEdit.setPlainText(self.subtask_state.stdout)
        self.gui.ui.subtaskErrorLogTextEdit.setPlainText(self.subtask_state.stderr)
        self.gui.ui.priceLabel.setText(u"{:.6f} ETH".format(self.subtask_state.value / denoms.ether))
        self.gui.ui.nodeIpAddressLabel.setText(self.subtask_state.computer.ip_address)
        self.__update_results()

    def __update_results(self):
        n = len(self.subtask_state.results)
        self.gui.ui.resultSlider.setMaximum(n)
        self.gui.ui.resultSlider.setEnabled(n > 1)
        self.gui.ui.showResultButton.setEnabled(n > 0)

    def __show_result_clicked(self):
        num = self.gui.ui.resultSlider.value() - 1
        self.show_file(self.subtask_state.results[num])
