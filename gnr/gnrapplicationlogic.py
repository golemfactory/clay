from __future__ import division
import cPickle
import logging
import os

from ethereum.utils import denoms
from PyQt4 import QtCore
from PyQt4.QtCore import QObject
from PyQt4.QtGui import QTableWidgetItem
from twisted.internet import task
from twisted.internet.defer import inlineCallbacks, returnValue

from golem.client import GolemClientEventListener, GolemClientRemoteEventListener
from golem.core.common import get_golem_path
from golem.core.simpleenv import SimpleEnv
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import TaskState
from golem.task.taskstate import TaskStatus

from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.benchmark.minilight.src.minilight import makePerfTest
from apps.rendering.task.renderingtaskstate import RenderingTaskState

from gnr.customizers.testingtaskprogresscustomizer import TestingTaskProgressDialogCustomizer
from gnr.customizers.updatingconfigdialogcustomizer import UpdatingConfigDialogCustomizer
from gnr.gnrtaskstate import GNRTaskState
from gnr.ui.dialog import TestingTaskProgressDialog, UpdatingConfigDialog

logger = logging.getLogger("gnr.app")


class GNRClientEventListener(GolemClientEventListener):
    def __init__(self, logic):
        self.logic = logic
        GolemClientEventListener.__init__(self)

    def task_updated(self, task_id):
        self.logic.task_status_changed(task_id)

    def check_network_state(self):
        self.logic.check_network_state()


class GNRClientRemoteEventListener(GolemClientRemoteEventListener):
    def __init__(self, service_info):
        GolemClientRemoteEventListener.__init__(self, service_info)

    def task_updated(self, task_id):
        assert self.remote_client
        self.remote_client.task_status_changed(task_id)

    def check_network_state(self):
        assert self.remote_client
        self.remote_client.check_network_state()


task_to_remove_status = [TaskStatus.aborted, TaskStatus.timeout, TaskStatus.finished, TaskStatus.paused]


class GNRApplicationLogic(QtCore.QObject):
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.tasks = {}
        self.test_tasks = {}
        self.task_types = {}
        self.customizer = None
        self.root_path = os.path.normpath(os.path.join(get_golem_path(), 'gnr'))
        self.nodes_manager_client = None
        self.client = None
        self.progress_dialog = None
        self.progress_dialog_customizer = None
        self.config_dialog = None
        self.config_dialog_customizer = None
        self.add_new_nodes_function = lambda x: None
        self.datadir = None
        self.res_dirs = None
        self.node_name = None
        self.br = None
        self.__looping_calls = None
        self.dir_manager = None
        self.reactor = None

    def start(self):
        task_status = task.LoopingCall(self.get_status)
        task_peers = task.LoopingCall(self.update_peers_view)
        task_payments = task.LoopingCall(self.update_payments_view)
        task_computing_stats = task.LoopingCall(self.update_stats)
        task_estimated_reputation = task.LoopingCall(self.update_estimated_reputation)
        task_status.start(3.0)
        task_peers.start(3.0)
        task_payments.start(5.0)
        task_computing_stats.start(3.0)
        task_estimated_reputation.start(60.0)
        self.__looping_calls = (task_peers, task_status, task_payments, task_computing_stats, task_estimated_reputation)

    def stop(self):
        for looping_call in self.__looping_calls:
            looping_call.stop()

    def register_gui(self, gui, customizer_class):
        self.customizer = customizer_class(gui, self)

    @inlineCallbacks
    def register_client(self, client, logic_service_info):
        event_listener = GNRClientRemoteEventListener(logic_service_info)

        self.client = client
        self.client.register_listener(event_listener)
        self.customizer.init_config()

        use_transaction_system = yield client.use_transaction_system()
        if use_transaction_system:
            payment_address = yield client.get_payment_address()
        else:
            payment_address = ""

        config = yield self.get_config()
        response = yield self.client.start_batch() \
            .get_description() \
            .get_client_id() \
            .get_datadir()   \
            .get_node_name() \
            .call()

        self.node_name = response.pop()
        self.datadir = response.pop()
        client_id = response.pop()
        description = response.pop()

        self.customizer.set_options(config, client_id, payment_address, description)
        if not self.node_name:
            self.customizer.prompt_node_name(config)
        self.dir_manager = DirManager(self.datadir)

    def register_start_new_node_function(self, func):
        self.add_new_nodes_function = func

    @inlineCallbacks
    def get_res_dirs(self):
        dirs = yield self.client.get_res_dirs()
        returnValue(dirs)

    def remove_computed_files(self):
        self.client.remove_computed_files()

    def remove_distributed_files(self):
        self.client.remove_distributed_files()

    def remove_received_files(self):
        self.client.remove_received_files()

    @inlineCallbacks
    def check_network_state(self):
        listen_port = yield self.client.get_p2p_port()
        task_server_port = yield self.client.get_task_server_port()
        if listen_port == 0 or task_server_port == 0:
            self.customizer.gui.ui.errorLabel.setText("Application not listening, check config file.")
            returnValue(None)

        peer_info = yield self.client.get_peer_info()
        peers_num = len(peer_info)

        if peers_num == 0:
            self.customizer.gui.ui.errorLabel.setText("Not connected to Golem Network. Check seed parameters.")
            returnValue(None)

        self.customizer.gui.ui.errorLabel.setText("")

    def get_task(self, task_id):
        assert task_id in self.tasks, "GNRApplicationLogic: task {} not added".format(task_id)

        return self.tasks[task_id]

    def get_task_types(self):
        return self.task_types

    @inlineCallbacks
    def get_status(self):
        client_status = yield self.client.get_status()
        self.customizer.gui.ui.statusTextBrowser.setText(client_status)

    def update_peers_view(self):
        self.client.get_peer_info().addCallback(self._update_peers_view)

    def _update_peers_view(self, peers):
        table = self.customizer.gui.ui.connectedPeersTable
        row_count = table.rowCount() if isinstance(table, QObject) else 0
        new_row_count = len(peers)

        if new_row_count < row_count:
            for i in xrange(row_count, new_row_count, -1):
                table.removeRow(i - 1)
        elif new_row_count > row_count:
            for i in xrange(row_count, new_row_count):
                table.insertRow(i)

        for i, peer in enumerate(peers):
            table.setItem(i, 0, QTableWidgetItem(peer.address))
            table.setItem(i, 1, QTableWidgetItem(str(peer.port)))
            table.setItem(i, 2, QTableWidgetItem(peer.key_id))
            table.setItem(i, 3, QTableWidgetItem(peer.node_name))

    def update_payments_view(self):
        self.client.get_balance().addCallback(self._update_payments_view)

    def _update_payments_view(self, result_tuple):
        if any(b is None for b in result_tuple):
            return
        b, ab, deposit = result_tuple

        rb = b - ab
        total = deposit + b
        fmt = "{:.6f} ETH"
        ui = self.customizer.gui.ui
        ui.localBalanceLabel.setText(fmt.format(b / denoms.ether))
        ui.availableBalanceLabel.setText(fmt.format(ab / denoms.ether))
        ui.reservedBalanceLabel.setText(fmt.format(rb / denoms.ether))
        ui.depositBalanceLabel.setText(fmt.format(deposit / denoms.ether))
        ui.totalBalanceLabel.setText(fmt.format(total / denoms.ether))

    @inlineCallbacks
    def update_estimated_reputation(self):
        use_ranking = yield self.client.use_ranking()
        if use_ranking:
            ui = self.customizer.gui.ui

            client_key = yield self.client.get_node_key()
            computing_trust = yield self.client.get_computing_trust(client_key)
            requesting_trust = yield self.client.get_requesting_trust(client_key)

            pro_rep = int(computing_trust * 100)
            req_rep = int(requesting_trust * 100)

            ui.estimatedProviderReputation.setText("{}%".format(pro_rep))
            ui.estimatedRequestorReputation.setText("{}%".format(req_rep))
        else:
            message = "Ranking system off"
            self.customizer.gui.ui.estimatedRequestorReputation.setText(message)
            self.customizer.gui.ui.estimatedProviderReputation.setText(message)

    @inlineCallbacks
    def update_stats(self):
        response = yield self.client.get_task_stats()

        self.customizer.gui.ui.knownTasks.setText(str(response['in_network']))
        self.customizer.gui.ui.supportedTasks.setText(str(response['supported']))
        self.customizer.gui.ui.computedTasks.setText(str(response['subtasks_computed']))
        self.customizer.gui.ui.tasksWithErrors.setText(str(response['subtasks_with_errors']))
        self.customizer.gui.ui.tasksWithTimeouts.setText(str(response['subtasks_with_timeout']))

    @inlineCallbacks
    def get_config(self):
        config = yield self.client.get_config()
        returnValue(config)

    def change_description(self, description):
        self.client.change_description(description)

    def quit(self):
        self.client.quit()

    def get_task_type(self, name):
        task_type = self.tasksType[name]
        if task_type:
            return task_type
        else:
            assert False, "Task {} not registered".format(name)

    def task_settings_changed(self):
        self.customizer.new_task_dialog_customizer.task_settings_changed()

    @inlineCallbacks
    def change_config(self, cfg_desc, run_benchmarks=False):
        yield self.client.change_config(cfg_desc, run_benchmarks=run_benchmarks)
        self.node_name = yield self.client.get_node_name()
        self.customizer.set_name(u"{}".format(self.node_name))

    def _get_new_task_state(self):
        return GNRTaskState()

    def start_task(self, task_id):
        ts = self.get_task(task_id)

        if ts.task_state.status != TaskStatus.notStarted:
            error_msg = "Task already started"
            self.show_error_window(error_msg)
            logger.error(error_msg)
            return

        tb = self.get_builder(ts)
        t = Task.build_task(tb)
        ts.task_state.status = TaskStatus.starting
        self.customizer.update_tasks(self.tasks)

        self.client.enqueue_new_task(t)

    def get_builder(self, task_state):
        # FIXME This is just temporary for solution for Brass
        if hasattr(task_state.definition, "renderer"):
            task_state.definition.task_type = task_state.definition.renderer

        builder = self.task_types[task_state.definition.task_type].task_builder_type(self.node_name,
                                                                                     task_state.definition,
                                                                                     self.datadir, self.dir_manager)
        return builder

    def restart_task(self, task_id):
        self.client.restart_task(task_id)

    def abort_task(self, task_id):
        self.client.abort_task(task_id)

    def pause_task(self, task_id):
        self.client.pause_task(task_id)

    def resume_task(self, task_id):
        self.client.resume_task(task_id)

    def delete_task(self, task_id):
        self.client.delete_task(task_id)
        self.customizer.remove_task(task_id)

    def show_task_details(self, task_id):
        self.customizer.show_details_dialog(task_id)

    def clone_task(self, task_id):
        self.customizer.clone_task(task_id)

    def restart_subtask(self, subtask_id):
        self.client.restart_subtask(subtask_id)

    def change_task(self, task_id):
        self.customizer.show_change_task_dialog(task_id)

    def show_task_result(self, task_id):
        self.customizer.show_task_result(task_id)

    @inlineCallbacks
    def get_keys_auth(self):
        keys_auth = yield self.client.get_keys_auth()
        returnValue(keys_auth)

    @inlineCallbacks
    def get_key_id(self):
        key_id = yield self.client.get_key_id()
        returnValue(key_id)

    @inlineCallbacks
    def get_difficulty(self):
        difficulty = yield self.client.get_difficulty()
        returnValue(difficulty)

    @inlineCallbacks
    def load_keys_from_file(self, file_name):
        result = yield self.client.load_keys_from_file(file_name)
        returnValue(result)

    @inlineCallbacks
    def save_keys_to_files(self, private_key_path, public_key_path):
        result = yield self.client.save_keys_to_files(private_key_path, public_key_path)
        returnValue(result)

    def change_timeouts(self, task_id, full_task_timeout, subtask_timeout):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.definition.full_task_timeout = full_task_timeout
            task.definition.subtask_timeout = subtask_timeout
            self.client.change_timeouts(task_id, full_task_timeout, subtask_timeout)
            self.customizer.update_task_additional_info(task)
        else:
            logger.error("It's not my task: {} ", task_id)

    def get_test_tasks(self):
        return self.test_tasks

    def add_task_from_definition(self, definition):
        task_state = self._get_new_task_state()
        task_state.status = TaskStatus.notStarted

        task_state.definition = definition

        self.add_tasks([task_state])

    def add_tasks(self, tasks):

        if len(tasks) == 0:
            return

        for t in tasks:
            if t.definition.task_id not in self.tasks:
                self.tasks[t.definition.task_id] = t
                self.customizer.add_task(t)
            else:
                self.tasks[t.definition.task_id] = t

        self.customizer.update_tasks(self.tasks)
        self.customizer.gui.ui.listWidget.setCurrentItem(self.customizer.gui.ui.listWidget.item(1))

    def register_new_task_type(self, task_type):
        if task_type.name not in self.task_types:
            self.task_types[task_type.name] = task_type
        else:
            assert False, "Task type {} already registered".format(task_type.name)

    def register_new_test_task_type(self, test_task_info):
        if test_task_info.name not in self.test_tasks:
            self.test_tasks[test_task_info.name] = test_task_info
        else:
            assert False, "Test task {} already registered".format(test_task_info.name)

    @staticmethod
    def save_task(task_state, file_path):
        path = u"{}".format(file_path)
        if not path.endswith(".gt"):
            if not path.endswith("."):
                file_path += "."
            file_path += "gt"
        with open(file_path, "wb") as f:
            tspickled = cPickle.dumps(task_state)
            f.write(tspickled)

    @staticmethod
    def recount_performance(num_cores):
        test_file = os.path.join(get_golem_path(), 'apps', 'core', 'benchmark', 'minilight', 'cornellbox.ml.txt')
        result_file = SimpleEnv.env_file_name("minilight.ini")
        estimated_perf = makePerfTest(test_file, result_file, num_cores)
        return estimated_perf

    def toggle_config_dialog(self, on=True):
        self.customizer.gui.setEnabled('new_task', not on)
        self.customizer.gui.setEnabled('settings', not on)  # disable 'change' and 'cancel' buttons

        if on:
            if not self.config_dialog_customizer:
                self.config_dialog = UpdatingConfigDialog(self.customizer.gui.window)
                self.config_dialog_customizer = UpdatingConfigDialogCustomizer(self.config_dialog, self)
                self.config_dialog.show()
        else:
            if self.config_dialog_customizer:
                self.config_dialog_customizer.close()
                self.config_dialog_customizer = None
                self.config_dialog = None

    def docker_config_changed(self):
        self.customizer.configuration_dialog_customizer.load_data()

    def run_test_task(self, task_state):
        if self._validate_task_state(task_state):

            self.progress_dialog = TestingTaskProgressDialog(self.customizer.gui.window)
            self.progress_dialog_customizer = TestingTaskProgressDialogCustomizer(self.progress_dialog, self)
            self.progress_dialog_customizer.enable_ok_button(False)    # disable 'ok' button
            self.progress_dialog_customizer.enable_abort_button(False) # disable 'abort' button
            self.progress_dialog_customizer.enable_close(False)        # prevent from closing
            self.progress_dialog_customizer.show_message("Preparing test...")
            def on_abort():
                self.progress_dialog_customizer.show_message("Aborting test...")
                self.abort_test_task()
            self.progress_dialog_customizer.gui.ui.abortButton.clicked.connect(on_abort)
            self.customizer.gui.setEnabled('new_task', False)  # disable everything on 'new task' tab
            self.progress_dialog.show()

            tb = self.get_builder(task_state)
            t = Task.build_task(tb)
            self.client.run_test_task(t)

            return True

        return False

    def test_task_started(self, success):
        self.progress_dialog_customizer.show_message("Testing...")
        self.progress_dialog_customizer.enable_abort_button(success)

    def abort_test_task(self):
        self.client.abort_test_task()

    # label param is the gui element to set text
    def run_benchmark(self, benchmark, label, cfg_param_name):
        task_state = RenderingTaskState()
        task_state.status = TaskStatus.notStarted
        task_state.definition = benchmark.query_benchmark_task_definition()
        self._validate_task_state(task_state)

        tb = self.get_builder(task_state)
        t = Task.build_task(tb)
        
        reactor = self.__get_reactor()

        self.br = BenchmarkRunner(t, self.datadir,
                                  lambda p: reactor.callFromThread(self._benchmark_computation_success, 
                                                                   performance=p, label=label, 
                                                                   cfg_param=cfg_param_name),
                                  self._benchmark_computation_error,
                                  benchmark)

        self.progress_dialog = TestingTaskProgressDialog(self.customizer.gui.window)
        self.progress_dialog_customizer = TestingTaskProgressDialogCustomizer(self.progress_dialog, self)
        self.progress_dialog_customizer.enable_ok_button(False) # disable 'ok' button
        self.customizer.gui.setEnabled('recount', False)        # disable all 'recount' buttons
        self.progress_dialog.show()

        self.br.start()

    @inlineCallbacks
    def _benchmark_computation_success(self, performance, label, cfg_param):
        self.progress_dialog.stop_progress_bar()
        self.progress_dialog_customizer.show_message(u"Recounted")
        self.progress_dialog_customizer.enable_ok_button(True)  # enable 'ok' button
        self.customizer.gui.setEnabled('recount', True)         # enable all 'recount' buttons

        # rounding
        perf = int((performance * 10) + 0.5) / 10.0
        yield self.client.update_setting(cfg_param, perf)
        label.setText(str(perf))

    def _benchmark_computation_error(self, error):
        self.progress_dialog.stop_progress_bar()
        self.progress_dialog_customizer.show_message(u"Recounting failed: {}".format(error))
        self.progress_dialog_customizer.enable_ok_button(True)  # enable 'ok' button
        self.customizer.gui.setEnabled('recount', True)         # enable all 'recount' buttons

    @inlineCallbacks
    def get_environments(self):
        environments = yield self.client.get_environments()
        returnValue(environments)

    def change_accept_tasks_for_environment(self, env_id, state):
        self.client.change_accept_tasks_for_environment(env_id, state)

    def test_task_computation_success(self, results, est_mem, msg=None):
        self.progress_dialog.stop_progress_bar()                # stop progress bar and set it's value to 100
        if msg is not None:
            from PyQt4.QtGui import QMessageBox
            ms_box = QMessageBox(QMessageBox.NoIcon, "Warning", u"{}".format(msg))
            ms_box.exec_()
            ms_box.show()
        msg = u"Task tested successfully"
        self.progress_dialog_customizer.show_message(msg)
        self.progress_dialog_customizer.enable_ok_button(True)    # enable 'ok' button
        self.progress_dialog_customizer.enable_close(True)
        self.progress_dialog_customizer.enable_abort_button(False)# disable 'abort' button
        self.customizer.gui.setEnabled('new_task', True)        # enable everything on 'new task' tab
        if self.customizer.new_task_dialog_customizer:
            self.customizer.new_task_dialog_customizer.test_task_computation_finished(True, est_mem)

    def test_task_computation_error(self, error):
        self.progress_dialog.stop_progress_bar()
        err_msg = u"Task test computation failure. "
        if error:
            err_msg += self.__parse_error_message(error)
        self.progress_dialog_customizer.show_message(err_msg)
        self.progress_dialog_customizer.enable_ok_button(True) # enable 'ok' button
        self.progress_dialog_customizer.enable_close(True)
        self.progress_dialog_customizer.enable_abort_button(False)# disable 'abort' button
        self.customizer.gui.setEnabled('new_task', True)  # enable everything on 'new task' tab
        if self.customizer.new_task_dialog_customizer:
            self.customizer.new_task_dialog_customizer.test_task_computation_finished(False, 0)

    @staticmethod
    def __parse_error_message(error_msg):
        if any(code in error_msg for code in ['246', '247', '500']):
            return u"[{}] There is a chance that you RAM limit is too low. Consider increasing max memory usage".format(
                error_msg)
        return u"{}".format(error_msg)

    @inlineCallbacks
    def task_status_changed(self, task_id):

        if task_id in self.tasks:
            ts = yield self.client.query_task_state(task_id)
            assert isinstance(ts, TaskState)
            self.tasks[task_id].task_state = ts
            self.customizer.update_tasks(self.tasks)
            if ts.status in task_to_remove_status:
                self.client.remove_task_header(task_id)
                self.client.remove_task(task_id)
        else:
            assert False, "Should never be here!"

        if self.customizer.current_task_highlighted.definition.task_id == task_id:
            self.customizer.update_task_additional_info(self.tasks[task_id])

    def key_changed(self):
        self.client.key_changed()

    @inlineCallbacks
    def get_payments(self):
        payments_list = yield self.client.get_payments_list()
        returnValue(payments_list)

    @inlineCallbacks
    def get_incomes(self):
        incomes_list = yield self.client.get_incomes_list()
        returnValue(incomes_list)

    @inlineCallbacks
    def get_max_price(self):
        """ Return suggested max price per hour of computation
        :return:
        """
        config = yield self.get_config()
        returnValue(config.max_price)

    @inlineCallbacks
    def get_cost_for_task_id(self, task_id):
        """
        Get cost of subtasks related with @task_id
        :param task_id: Task ID
        :return: Cost of the task
        """
        cost = yield self.client.get_payment_for_task_id(task_id)
        returnValue(cost)

    def show_error_window(self, text):
        from PyQt4.QtGui import QMessageBox
        ms_box = QMessageBox(QMessageBox.Critical, "Error", u"{}".format(text))
        ms_box.exec_()
        ms_box.show()

    def _validate_task_state(self, task_state):
        td = task_state.definition
        if not os.path.exists(td.main_program_file):
            self.show_error_window(u"Main program file does not exist: {}".format(td.main_program_file))
            return False
        return True

    @staticmethod
    def _format_stats_message(stat):
        try:
            return u"Session: {}; All time: {}".format(stat[0], stat[1])
        except (IndexError, TypeError) as err:
            logger.warning("Problem with stat formatin {}".format(err))
            return u"Error"

    def __get_reactor(self):
        if not self.reactor:
            from twisted.internet import reactor
            self.reactor = reactor
        return self.reactor
