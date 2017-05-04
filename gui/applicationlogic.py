from __future__ import division

import jsonpickle
import logging
import os

from PyQt5.QtCore import Qt
from ethereum.utils import denoms
from PyQt5 import QtCore
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox
from twisted.internet import task
from twisted.internet.defer import inlineCallbacks, returnValue

from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.benchmark.minilight.src.minilight import makePerfTest
from apps.core.task.coretaskstate import TaskDesc

from golem.core.common import get_golem_path
from golem.core.simpleenv import SimpleEnv
from golem.core.simpleserializer import DictSerializer
from golem.interface.client.logic import AppLogic
from golem.resource.dirmanager import DirManager, DirectoryType
from golem.task.taskbase import Task
from golem.task.taskstate import TaskState
from golem.task.taskstate import TaskStatus

from gui.controller.testingtaskprogresscustomizer import TestingTaskProgressDialogCustomizer
from gui.controller.updatingconfigdialogcustomizer import UpdatingConfigDialogCustomizer
from gui.view.dialog import TestingTaskProgressDialog, UpdatingConfigDialog

logger = logging.getLogger("app")


task_to_remove_status = [TaskStatus.aborted, TaskStatus.timeout, TaskStatus.finished, TaskStatus.paused]


class GuiApplicationLogic(QtCore.QObject, AppLogic):
    def __init__(self):
        QtCore.QObject.__init__(self)
        AppLogic.__init__(self)
        self.tasks = {}
        self.test_tasks = {}
        self.customizer = None
        self.root_path = os.path.normpath(os.path.join(get_golem_path(), 'gui'))
        self.nodes_manager_client = None
        self.client = None
        self.progress_dialog = None
        self.progress_dialog_customizer = None
        self.config_dialog = None
        self.config_dialog_customizer = None
        self.add_new_nodes_function = lambda x: None
        self.res_dirs = None
        self.br = None
        self.__looping_calls = None
        self.reactor = None
        self.options = None  # Current task options #FIXME - is it really needed?
        self.current_task_type = None  # Which task type is currently active
        self.default_task_type = None  # Which task type should be displayed first

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
    def register_client(self, client):
        # client is golem.rpc.session.Client
        datadir = yield client.get_datadir()
        config_dict = yield client.get_settings()
        client_id = yield client.get_key_id()
        payment_address = yield client.get_payment_address()
        description = yield client.get_description()

        config = DictSerializer.load(config_dict)

        self.client = client
        self.datadir = datadir
        self.node_name = config.node_name
        self.dir_manager = DirManager(self.datadir)

        self.customizer.init_config()
        self.customizer.set_options(config, client_id, payment_address, description)

        if not self.node_name:
            self.customizer.prompt_node_name(self.node_name)

    def register_start_new_node_function(self, func):
        self.add_new_nodes_function = func

    @inlineCallbacks
    def get_res_dirs(self):
        dirs = yield self.client.get_res_dirs()
        returnValue(dirs)

    def remove_computed_files(self):
        self.client.clear_dir(DirectoryType.COMPUTED)

    def remove_distributed_files(self):
        self.client.clear_dir(DirectoryType.DISTRIBUTED)

    def remove_received_files(self):
        self.client.clear_dir(DirectoryType.RECEIVED)

    def connection_status_changed(self, message):
        self.customizer.gui.ui.errorLabel.setText(message)

    def get_task(self, task_id):
        if task_id not in self.tasks:
            raise AttributeError("GuiApplicationLogic: task {} not added".format(task_id))
        return self.tasks[task_id]

    def get_task_types(self):
        return self.task_types

    def get_current_task_type(self):
        """
        :return str: id of a currently active task type
        """
        return self.current_task_type

    def get_default_task_type(self):
        return self.default_task_type

    @inlineCallbacks
    def get_status(self):
        client_status = yield self.client.get_status()
        self.customizer.gui.ui.statusTextBrowser.setText(client_status)

    def update_peers_view(self):
        self.client.get_connected_peers().addCallbacks(
            self._update_peers_view, self._rpc_error
        )

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
            table.setItem(i, 0, QTableWidgetItem(peer['address']))
            table.setItem(i, 1, QTableWidgetItem(str(peer['port'])))
            table.setItem(i, 2, QTableWidgetItem(peer['key_id']))
            table.setItem(i, 3, QTableWidgetItem(peer['node_name']))

    def update_payments_view(self):
        self.client.get_balance().addCallbacks(
            self._update_payments_view, self._rpc_error
        )

    def _update_payments_view(self, result_tuple):
        if any(b is None for b in result_tuple):
            return
        gnt_balance, gnt_available, eth_balance = result_tuple
        gnt_balance = int(gnt_balance)
        gnt_available = int(gnt_available)
        eth_balance = int(eth_balance)

        gnt_reserved = gnt_balance - gnt_available
        ui = self.customizer.gui.ui
        ui.localBalanceLabel.setText("{:.8f} GNT".format(gnt_balance / denoms.ether))
        ui.availableBalanceLabel.setText("{:.8f} GNT".format(gnt_available / denoms.ether))
        ui.reservedBalanceLabel.setText("{:.8f} GNT".format(gnt_reserved / denoms.ether))
        ui.depositBalanceLabel.setText("{:.8f} ETH".format(eth_balance / denoms.ether))
        ui.totalBalanceLabel.setText("N/A")

    @staticmethod
    def _rpc_error(error):
        logger.error("GUI RPC error: {}".format(error))

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
        config_dict = yield self.client.get_settings()
        returnValue(DictSerializer.load(config_dict))

    def change_description(self, description):
        self.client.change_description(description)

    def quit(self):
        self.client.quit()

    def get_task_type(self, name):
        if name in self.task_types:
            return self.task_types[name]
        else:
            raise RuntimeError("Task {} not registered".format(name))

    def task_settings_changed(self):
        self.customizer.new_task_dialog_customizer.task_settings_changed()

    @inlineCallbacks
    def change_node_name(self, node_name):
        yield self.client.update_setting('node_name', node_name)
        self.node_name = node_name
        self.customizer.set_name(u"{}".format(self.node_name))

    @inlineCallbacks
    def change_config(self, cfg_desc, run_benchmarks=False):
        cfg_dict = DictSerializer.dump(cfg_desc)
        yield self.client.update_settings(cfg_dict, run_benchmarks=run_benchmarks)
        self.node_name = yield self.client.get_setting('node_name')
        self.customizer.set_name(u"{}".format(self.node_name))

    def start_task(self, task_id):
        ts = self.get_task(task_id)

        if ts.task_state.status != TaskStatus.notStarted:
            error_msg = "Task already started"
            self.customizer.show_error_window(error_msg)
            logger.error(error_msg)
            return

        def cbk(task):
            ts.task_state.outputs = task.get_output_names()
            ts.task_state.status = TaskStatus.starting
            self.customizer.update_tasks(self.tasks)
        self.client.create_task(self.build_and_serialize_task(ts, cbk))

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
            logger.error("It's not my task: {}".format(task_id))

    def get_test_tasks(self):
        return self.test_tasks

    def add_task_from_definition(self, definition):
        task_state = TaskDesc()
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
        AppLogic.register_new_task_type(self, task_type)
        if len(self.task_types) == 1:
            self.default_task_type = task_type

    def register_new_test_task_type(self, test_task_info):
        if test_task_info.name not in self.test_tasks:
            self.test_tasks[test_task_info.name] = test_task_info
        else:
            raise RuntimeError("Test task {} already registered".format(test_task_info.name))

    @staticmethod
    def save_task(task_state, file_path):
        path = u"{}".format(file_path)
        if not path.endswith(".gt"):
            if not path.endswith("."):
                file_path += "."
            file_path += "gt"
        with open(file_path, "wb") as f:
            data = jsonpickle.dumps(task_state)
            f.write(data)

    @staticmethod
    def recount_performance(num_cores):
        test_file = os.path.join(get_golem_path(), 'apps', 'core', 'benchmark', 'minilight', 'cornellbox.ml.txt')
        result_file = SimpleEnv.env_file_name("minilight.ini")
        estimated_perf = makePerfTest(test_file, result_file, num_cores)
        return estimated_perf

    def lock_config(self, on=True):

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

    def config_changed(self):
        self.customizer.configuration_dialog_customizer.load_data()

    def run_test_task(self, task_state):
        if self._validate_task_state(task_state):

            def on_abort():
                self.progress_dialog_customizer.show_message("Aborting test...")
                self.abort_test_task()

            self.progress_dialog = TestingTaskProgressDialog(self.customizer.gui.window)
            self.progress_dialog_customizer = TestingTaskProgressDialogCustomizer(self.progress_dialog, self)
            self.progress_dialog_customizer.enable_ok_button(False)    # disable 'ok' button
            self.progress_dialog_customizer.enable_abort_button(False) # disable 'abort' button
            self.progress_dialog_customizer.enable_close(False)        # prevent from closing
            self.progress_dialog_customizer.show_message("Preparing test...")
            self.progress_dialog_customizer.gui.ui.abortButton.clicked.connect(on_abort)
            self.customizer.gui.setEnabled('new_task', False)  # disable everything on 'new task' tab
            self.progress_dialog.show()

            try:
                self.client.run_test_task(self.build_and_serialize_task(task_state))
                return True
            except Exception as ex:
                self.test_task_computation_error(ex)

        return False

    def build_and_serialize_task(self, task_state, cbk=None):
        tb = self.get_builder(task_state)
        t = Task.build_task(tb)
        t.header.max_price = str(t.header.max_price)
        t_serialized = DictSerializer.dump(t)
        if 'task_definition' in t_serialized:
            t_serialized_def = t_serialized['task_definition']
            t_serialized_def['resources'] = list(t_serialized_def['resources'])
            if 'max_price' in t_serialized_def:
                t_serialized_def['max_price'] = str(t_serialized_def['max_price'])
        from pprint import pformat
        logger.debug('task serialized: %s', pformat(t_serialized))
        if cbk:
            cbk(t)
        return t_serialized

    def test_task_started(self, success):
        self.progress_dialog_customizer.show_message("Testing...")
        self.progress_dialog_customizer.enable_abort_button(success)

    def abort_test_task(self):
        self.client.abort_test_task()

    # label param is the gui element to set text
    def run_benchmark(self, benchmark, label, cfg_param_name):
        task_state = TaskDesc()
        task_state.status = TaskStatus.notStarted
        task_state.definition = benchmark.task_definition
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

        self.br.run()

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

    # TODO Move this function to new task dialog
    def change_verification_option(self, size_x_max=None, size_y_max=None):
        if size_x_max:
            self.customizer.gui.ui.verificationSizeXSpinBox.setMaximum(size_x_max)
        if size_y_max:
            self.customizer.gui.ui.verificationSizeYSpinBox.setMaximum(size_y_max)

    def enable_environment(self, env_id):
        self.client.enable_environment(env_id)

    def disable_environment(self, env_id):
        self.client.disable_environment(env_id)

    def test_task_computation_success(self, results, est_mem, time_spent,  msg=None):
        self.progress_dialog.stop_progress_bar()                # stop progress bar and set it's value to 100
        self.progress_dialog_customizer.enable_ok_button(True)  # enable 'ok' button
        self.progress_dialog_customizer.enable_close(True)
        self.progress_dialog_customizer.enable_abort_button(False)  # disable 'abort' button

        if msg is not None:
            self.progress_dialog.close()
            self.customizer.show_warning_window(u"{}".format(msg))
        else:
            msg = u"Task tested successfully - time %.2f" % time_spent
            self.progress_dialog_customizer.show_message(msg)

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
            ts_dict = yield self.client.query_task_state(task_id)
            ts = DictSerializer.load(ts_dict)
            if not isinstance(ts, TaskState):
                raise TypeError("Incorrect task state type: {}. Should be TaskState".format(ts))
            self.tasks[task_id].task_state = ts
            self.customizer.update_tasks(self.tasks)
            if ts.status in task_to_remove_status:
                self.client.remove_task_header(task_id)
                self.client.remove_task(task_id)
        else:
            logger.warning("Unknown task_id {}".format(task_id))

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
        max_price = yield self.client.get_setting('max_price')
        returnValue(max_price)

    @inlineCallbacks
    def get_cost_for_task_id(self, task_id):
        """
        Get cost of subtasks related with @task_id
        :param task_id: Task ID
        :return: Cost of the task
        """

        cost = yield self.client.get_task_cost(task_id)
        returnValue(cost)

    def set_current_task_type(self, name):
        if name in self.task_types:
            self.current_task_type = self.task_types[name]
        else:
            logger.error("Unknown task type chosen {}, known task_types: {}".format(name, self.task_types))

    def _validate_task_state(self, task_state):
        td = task_state.definition
        if td.task_type not in self.task_types:
            self.customizer.show_error_window(u"{}".format("Task {} is not registered".format(td.task_type)))
            return False
        is_valid, err = td.is_valid()
        if is_valid and err:
            self.customizer.show_warning_window(u"{}".format(err))
        if not is_valid:
            self.customizer.show_error_window(u"{}".format(err))
        return is_valid

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
