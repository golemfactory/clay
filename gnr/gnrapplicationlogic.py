import os
import logging
import cPickle

from PyQt4 import QtCore
from twisted.internet import task

from golem.task.taskstate import TaskStatus
from golem.task.taskbase import Task
from golem.task.taskstate import TaskState
from golem.core.common import get_golem_path
from golem.core.simpleenv import SimpleEnv
from golem.client import GolemClientEventListener
from golem.manager.client.nodesmanagerclient import NodesManagerUidClient, NodesManagerClient

from gnr.ui.dialog import TestingTaskProgressDialog
from gnr.customizers.testingtaskprogresscustomizer import TestingTaskProgressDialogCustomizer
from gnr.renderingdirmanager import get_benchmarks_path
from gnr.gnrtaskstate import GNRTaskState
from gnr.task.tasktester import TaskTester

from gnr.benchmarks.luxrender.lux_test import lux_performance
from gnr.benchmarks.blender.blender_test import blender_performance

from gnr.benchmarks.minilight.src.minilight import makePerfTest

logger = logging.getLogger(__name__)


class GNRClientEventListener(GolemClientEventListener):
    def __init__(self, logic):
        self.logic = logic
        GolemClientEventListener.__init__(self)

    def task_updated(self, task_id):
        self.logic.task_status_changed(task_id)

    def check_network_state(self):
        self.logic.check_network_state()


task_to_remove_status = [TaskStatus.aborted, TaskStatus.failure, TaskStatus.finished, TaskStatus.paused]


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
        self.tt = None
        self.progress_dialog = None
        self.progress_dialog_customizer = None
        self.add_new_nodes_function = lambda x: None

    def start(self):
        l = task.LoopingCall(self.get_status)
        l.start(3.0)

    def register_gui(self, gui, customizer_class):
        self.customizer = customizer_class(gui, self)

    def register_client(self, client):
        self.client = client
        self.client.register_listener(GNRClientEventListener(self))
        self.customizer.init_config()
        payment_address = ""
        if client.transaction_system:
            payment_address = client.transaction_system.get_payment_address()
        self.customizer.set_options(self.get_config(), client.keys_auth.get_key_id(),
                                    payment_address)

    def register_start_new_node_function(self, func):
        self.add_new_nodes_function = func

    def get_res_dirs(self):
        return self.client.get_res_dirs()

    def remove_computed_files(self):
        self.client.remove_computed_files()

    def remove_distributed_files(self):
        self.client.remove_distributed_files()

    def remove_received_files(self):
        self.client.remove_received_files()

    def check_network_state(self):
        listen_port = self.client.p2pservice.cur_port
        task_server_port = self.client.task_server.cur_port
        if listen_port == 0 or task_server_port == 0:
            self.customizer.gui.ui.errorLabel.setText("Application not listening, check config file.")
            return
        peers_num = len(self.client.p2pservice.peers)
        if peers_num == 0:
            self.customizer.gui.ui.errorLabel.setText("Not connected to Golem Network. Check seed parameters.")
            return

        self.customizer.gui.ui.errorLabel.setText("")

    def start_nodes_manager_client(self):
        if self.client:
            config_desc = self.client.config_desc
            self.nodes_manager_client = NodesManagerUidClient(config_desc.node_name,
                                                              config_desc.manager_address,
                                                              config_desc.manager_port,
                                                              None,
                                                              self)
            self.nodes_manager_client.start()
            self.client.register_nodes_manager_client(self.nodes_manager_client)
        else:
            logger.error("Can't register nodes manager client. No client instance.")

    def get_task(self, task_id):
        assert task_id in self.tasks, "GNRApplicationLogic: task {} not added".format(task_id)

        return self.tasks[task_id]

    def get_task_types(self):
        return self.task_types

    def get_status(self):
        self.customizer.gui.ui.statusTextBrowser.setText(self.client.get_status())

    def get_config(self):
        return self.client.config_desc

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

    def change_config(self, cfg_desc):
        self.client.change_config(cfg_desc)

    def _get_new_task_state(self):
        return GNRTaskState()

    def start_task(self, task_id):
        ts = self.get_task(task_id)

        if ts.task_state.status != TaskStatus.notStarted:
            error_msg = "Task already started"
            self.show_error_window(error_msg)
            logger.error(error_msg)
            return

        tb = self._get_builder(ts)

        t = Task.build_task(tb)

        self.client.enqueue_new_task(t)

    def _get_builder(self, task_state):
        # FIXME Bardzo tymczasowe rozwiazanie dla zapewnienia zgodnosci
        if hasattr(task_state.definition, "renderer"):
            task_state.definition.task_type = task_state.definition.renderer

        return self.task_types[task_state.definition.task_type].task_builder_type(self.client.get_node_name(),
                                                                                  task_state.definition,
                                                                                  self.client.datadir)

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

    def get_keys_auth(self):
        return self.client.keys_auth

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

    def save_task(self, task_state, file_path):
        with open(file_path, "wb") as f:
            tspickled = cPickle.dumps(task_state)
            f.write(tspickled)

    def recount_performance(self, num_cores):
        test_file = os.path.join(get_benchmarks_path(), 'minilight', 'cornellbox.ml.txt')
        result_file = SimpleEnv.env_file_name("minilight.ini")
        estimated_perf = makePerfTest(test_file, result_file, num_cores)
        return estimated_perf

    def recount_lux_performance(self):
        cfg_filename = SimpleEnv.env_file_name("lux.ini")

        cfg_file = open(cfg_filename, 'w')
        average = lux_performance()
        cfg_file.write("{0:.1f}".format(average))
        cfg_file.close()

        return average

    def recount_blender_performance(self):
        cfg_filename = SimpleEnv.env_file_name("blender.ini")

        cfg_file = open(cfg_filename, 'w')
        average = blender_performance()
        cfg_file.write("{0:.1f}".format(average))
        cfg_file.close()

        return average

    def run_test_task(self, task_state):
        if self._validate_task_state(task_state):

            tb = self._get_builder(task_state)

            t = Task.build_task(tb)

            self.tt = TaskTester(t, self.client.datadir, self._test_task_computation_success,
                                 self._test_task_computation_error)

            self.progress_dialog = TestingTaskProgressDialog(self.customizer.gui.window)
            self.progress_dialog_customizer = TestingTaskProgressDialogCustomizer(self.progress_dialog, self)
            self.progress_dialog.show()

            self.tt.run()

            return True
        else:
            return False

    def get_environments(self):
        return self.client.get_environments()

    def change_accept_tasks_for_environment(self, env_id, state):
        self.client.change_accept_tasks_for_environment(env_id, state)

    def _test_task_computation_success(self, results, est_mem):
        self.progress_dialog_customizer.show_message("Test task computation success!")
        if self.customizer.new_task_dialog_customizer:
            self.customizer.new_task_dialog_customizer.test_task_computation_finished(True, est_mem)

    def _test_task_computation_error(self, error):
        err_msg = "Task test computation failure. " + error
        self.progress_dialog_customizer.show_message(err_msg)
        if self.customizer.new_task_dialog_customizer:
            self.customizer.new_task_dialog_customizer.test_task_computation_finished(False, 0)

    def task_status_changed(self, task_id):

        if task_id in self.tasks:
            ts = self.client.query_task_state(task_id)
            assert isinstance(ts, TaskState)
            self.tasks[task_id].task_state = ts
            self.customizer.update_tasks(self.tasks)
            if ts.status in task_to_remove_status:
                self.client.task_server.remove_task_header(task_id)
                self.client.p2pservice.remove_task(task_id)
        else:
            assert False, "Should never be here!"

        if self.customizer.current_task_highlighted.definition.task_id == task_id:
            self.customizer.update_task_additional_info(self.tasks[task_id])

    def key_changed(self):
        self.client.key_changed()

    def get_payments(self):
        if self.client.transaction_system:
            return self.client.transaction_system.get_payments_list()
        return ()

    def get_incomes(self):
        if self.client.transaction_system:
            return self.client.transaction_system.get_incomes_list()
        return ()

    def get_max_price(self):
        """ Return suggested max price per hour of computation
        :return:
        """
        return self.get_config().max_price

    def show_error_window(self, text):
        from PyQt4.QtGui import QMessageBox
        ms_box = QMessageBox(QMessageBox.Critical, "Error", text)
        ms_box.exec_()
        ms_box.show()

    def _validate_task_state(self, task_state):

        td = task_state.definition
        if not os.path.exists(td.main_program_file):
            self.show_error_window("Main program file does not exist: {}".format(td.main_program_file))
            return False
        return True
