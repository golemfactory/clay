#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import uuid

from ethereum.utils import denoms
from mock import Mock, ANY, call, patch
from twisted.internet.defer import Deferred

import golem
from apps.blender.benchmark.benchmark import BlenderBenchmark
from apps.core.task.coretask import CoreTaskBuilder
from apps.core.task.coretaskstate import TaskDesc, TaskDefinition
from golem import rpc
from golem.client import Client
from golem.core.deferred import sync_wait
from golem.core.simpleserializer import DictSerializer
from golem.interface.client.logic import logger as int_logger
from golem.resource.dirmanager import DirManager
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import Task, ComputeTaskDef, TaskHeader
from golem.task.taskstate import TaskStatus, TaskTestStatus, TaskState
from golem.testutils import DatabaseFixture
from golem.tools.assertlogs import LogTestCase
from golem.tools.ci import ci_skip
from golem.tools.testwithreactor import TestDirFixtureWithReactor
from gui.application import Gui
from gui.applicationlogic import (GuiApplicationLogic, logger,
                                  task_to_remove_status)
from gui.controller.mainwindowcustomizer import MainWindowCustomizer
from gui.startapp import register_task_types
from gui.view.appmainwindow import AppMainWindow


class TTask(Task):
    def __init__(self):
        Task.__init__(self, Mock(), Mock())
        self.src_code = ""
        self.extra_data = {}
        self.test_finished = False
        self.results = None
        self.tmp_dir = None

    def query_extra_data_for_test_task(self):
        ctd = ComputeTaskDef()
        ctd.subtask_id = "xxyyzz"
        ctd.task_id = "xyz"
        ctd.working_directory = self.header.root_path
        ctd.src_code = self.src_code
        ctd.extra_data = self.extra_data
        ctd.short_description = ""
        return ctd

    def after_test(self, results, tmp_dir):
        self.test_finished = True
        self.results = results
        self.tmp_dir = tmp_dir
        return {}

    def get_output_names(self):
        return ["output1", "output2", "output3"]


class TTaskWithDef(TTask):
    def __init__(self):
        super(TTaskWithDef, self).__init__()
        self.task_definition = TaskDefinition()
        self.task_definition.max_price = 100 * denoms.ether


class TTaskBuilder(CoreTaskBuilder):

    def __init__(self, path, task_class=TTask):
        self.path = path
        self.src_code = "output = {'data': n, 'result_type': 0}"
        self.extra_data = {"n": 421}
        self.task_class = task_class

    def build(self):
        t = self.task_class()
        t.header = TaskHeader(
            node_name="node1",
            task_id="xyz",
            task_owner_address="127.0.0.1",
            task_owner_port=45000,
            task_owner_key_id="key2",
            environment="test",
            max_price=30 * denoms.ether
        )
        t.header.root_path = self.path
        t.src_code = self.src_code
        t.extra_data = self.extra_data
        return t


class RPCClient(object):

    def __init__(self):
        self.success = False
        self.error = False
        self.started = False

    def test_task_computation_success(self, *args, **kwargs):
        self.success = True
        self.error = False
        self.started = False

    def test_task_computation_error(self, *args, **kwargs):
        self.success = False
        self.error = True
        self.started = False

    def test_task_started(self, *args, **kwargs):
        self.started = args[0]


class MockRPCSession(object):

    def __init__(self, called_object, method_map):

        self.connected = True
        self.success = None

        self.called_object = called_object
        self.method_map = method_map
        self.reverse_map = dict()

        for k, v in list(method_map.items()):
            self.reverse_map[v] = k

    def call(self, alias, *args, **kwargs):

        self.success = None
        method = getattr(self.called_object, self.reverse_map[alias])

        deferred = Deferred()

        try:
            result = method(*args, **kwargs)
        except Exception as exc:
            self.success = False
            deferred.errback(exc)
        else:
            self.success = True
            deferred.callback(result)

        return deferred

    def is_open(self):
        return self.connected


class MockRPCPublisher(object):

    def __init__(self):
        self.success = None

    def publish(self, alias, *args, **kwargs):

        if args and args[0] == TaskTestStatus.success:
            self.success = True
        elif args and args[0] == TaskTestStatus.error:
            self.success = False

    def reset(self):
        self.success = None


class TestGuiApplicationLogic(DatabaseFixture):

    def test_root_path(self):
        logic = GuiApplicationLogic()
        self.assertTrue(os.path.isdir(logic.root_path))

    def test_update_payments_view(self):
        logic = GuiApplicationLogic()
        logic.client = Mock()
        logic.customizer = Mock()
        ether = denoms.ether

        balance_deferred = Deferred()
        balance_deferred.result = (3 * ether, 1 * ether, 0.3 * ether)
        balance_deferred.called = True

        logic.client.get_balance.return_value = balance_deferred
        logic.update_payments_view()

        ui = logic.customizer.gui.ui
        ui.localBalanceLabel.setText.assert_called_once_with("3.00000000 GNT")
        ui.reservedBalanceLabel.setText.assert_called_once_with(
            "2.00000000 GNT")
        ui.availableBalanceLabel.setText.assert_called_once_with(
            "1.00000000 GNT")
        ui.depositBalanceLabel.setText.assert_called_once_with("0.30000000 ETH")

    def test_update_stats(self):
        logic = GuiApplicationLogic()
        logic.client = Mock()
        logic.customizer = Mock()

        deferred = Deferred()
        deferred.callback(None)
        logic.client.get_task_stats.return_value = deferred

        logic.update_stats()
        assert not logic.customizer.gui.ui.knownTasks.setText.called

        result = {
            'in_network': 1,
            'supported': 2,
            'subtasks_computed': 3,
            'subtasks_with_errors': 4,
            'subtasks_with_timeout': 5,
        }

        deferred = Deferred()
        deferred.callback(result)
        logic.client.get_task_stats.return_value = deferred

        logic.update_stats()
        logic.customizer.gui.ui.knownTasks.setText.assert_called_with(
            str(result['in_network']))

    def test_start_task(self):
        logic = GuiApplicationLogic()
        logic.customizer = Mock()
        logic.client = Mock()
        task_desc = TaskDesc()
        task_desc.task_state.status = TaskStatus.notStarted
        task_desc.definition.task_type = "TASKTYPE1"
        task_type = Mock()
        task_type.task_builder_type.return_value = TTaskBuilder(self.path)
        logic.task_types["TASKTYPE1"] = task_type
        logic.tasks["xyz"] = task_desc
        logic.start_task("xyz")
        assert task_desc.task_state.status == TaskStatus.starting
        assert task_desc.task_state.outputs == ["output1", "output2", "output3"]


class TestGuiApplicationLogicWithClient(DatabaseFixture, LogTestCase):

    def setUp(self):
        DatabaseFixture.setUp(self)
        LogTestCase.setUp(self)
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False,
                             use_docker_machine_manager=False,
                             use_monitor=False)

    def tearDown(self):
        self.client.quit()
        LogTestCase.tearDown(self)
        DatabaseFixture.tearDown(self)

    def test_change_description(self):
        logic = GuiApplicationLogic()
        logic.customizer = Mock()

        rpc_session = MockRPCSession(self.client, CORE_METHOD_MAP)
        rpc_client = rpc.session.Client(rpc_session, CORE_METHOD_MAP)

        description = "New description"

        logic.client = rpc_client
        logic.change_description(description)
        self.assertEqual(self.client.get_description(), description)

        p = logic.get_task_presets("Blender")
        assert p.result == {}
        logic.save_task_preset("NewPreset", "Blender", "Some data")
        p = logic.get_task_presets("Blender")
        assert p.result == {'NewPreset': "Some data"}
        logic.delete_task_preset("Blender", "NewPreset")
        p = logic.get_task_presets("Blender")
        assert p.result == {}

    def test_change_config(self):
        logic = GuiApplicationLogic()
        logic.customizer = Mock()

        rpc_session = MockRPCSession(self.client, CORE_METHOD_MAP)
        rpc_client = rpc.session.Client(rpc_session, CORE_METHOD_MAP)

        logic.client = rpc_client
        logic.change_config(dict(node_name='node_name'))

    def test_add_tasks(self):
        logic = GuiApplicationLogic()
        logic.customizer = Mock()
        td = TestGuiApplicationLogicWithClient._get_task_definition()
        logic.add_task_from_definition(td)
        self.assertIn("xyz", logic.tasks, "Task was not added")
        task_state1 = TestGuiApplicationLogicWithClient._get_task_state()
        task_state2 = TestGuiApplicationLogicWithClient._get_task_state(
            task_id="abc")
        task_state3 = TestGuiApplicationLogicWithClient._get_task_state(
            task_id="def")
        logic.add_tasks([task_state1, task_state2, task_state3])
        self.assertEqual(len(logic.tasks), 3, "Incorrect number of tasks")
        self.assertIn("xyz", logic.tasks, "Task was not added")
        self.assertIn("abc", logic.tasks, "Task was not added")
        self.assertIn("def", logic.tasks, "Task was not added")
        self.assertEqual(logic.tasks["xyz"].definition.full_task_timeout, 100,
                         "Wrong task timeout")
        self.assertEqual(logic.tasks["xyz"].definition.subtask_timeout, 50,
                         "Wrong subtask timeout")
        result = logic.add_tasks([])
        self.assertIsNone(result, "Returned value [{}] is not None".format(
            result))
        result = logic.get_test_tasks()
        self.assertEqual(result, {}, "Returned value is not empty")
        with self.assertLogs(logger):
            logic.change_timeouts("invalid", 10, 10)

        logic.config_changed()

    def test_task_status_changed(self):
        task_state = TaskState()
        task_dict = DictSerializer.dump(task_state)

        logic = GuiApplicationLogic()
        logic.tasks = dict(
            task_id=task_state,
            wrong_task=None
        )

        def get_logic_task(task_id):
            deferred = Deferred()
            task = logic.tasks.get(task_id)
            deferred.callback(DictSerializer.dump(task))
            return deferred

        logic.client = Mock()
        logic.client.query_task_state = Mock()
        logic.client.query_task_state.side_effect = get_logic_task

        logic.customizer = Mock()

        logic.task_status_changed('wrong_task')
        assert not logic.customizer.update_tasks.called
        assert logic.client.query_task_state.called

        logic.client.query_task_state.called = False
        logic.customizer.current_task_highlighted.definition.task_id = \
            str(uuid.uuid4())
        logic.task_status_changed(str(uuid.uuid4()))
        assert not logic.client.query_task_state.called
        assert not logic.customizer.update_task_additional_info.called

        logic.customizer.current_task_highlighted.definition.task_id = 'task_id'
        logic.task_status_changed(str(uuid.uuid4()))
        assert not logic.client.query_task_state.called
        assert not logic.customizer.update_task_additional_info.called

        logic.task_status_changed('task_id')
        assert logic.client.query_task_state.called
        assert logic.customizer.update_task_additional_info.called
        assert not logic.client.delete_task.called

        task_state.status = task_to_remove_status[0]
        logic.task_status_changed('task_id')
        assert logic.client.query_task_state.called
        assert logic.customizer.update_task_additional_info.called
        assert logic.client.delete_task.called

    @ci_skip
    def test_get_environments(self):
        from apps.appsmanager import AppsManager

        logic = GuiApplicationLogic()
        logic.customizer = Mock()
        logic.client = self.client

        apps_manager = AppsManager()
        apps_manager.load_apps()

        for env in apps_manager.get_env_list():
            self.client.environments_manager.add_environment(env)

        environments = sync_wait(logic.get_environments())

        assert len(environments) > 0
        assert all([bool(env) for env in environments])
        assert all([isinstance(env, dict) for env in environments])

    @staticmethod
    def _get_task_state(task_id="xyz", full_task_timeout=100,
                        subtask_timeout=50):
        task_state = TaskDesc()
        td = TestGuiApplicationLogicWithClient._get_task_definition(
            task_id=task_id, full_task_timeout=full_task_timeout,
            subtask_timeout=subtask_timeout)
        task_state.status = TaskStatus.notStarted
        task_state.definition = td
        return task_state

    @staticmethod
    def _get_task_definition(task_id="xyz", full_task_timeout=100,
                             subtask_timeout=50):
        td = TaskDefinition()
        td.task_id = task_id
        td.full_task_timeout = full_task_timeout
        td.subtask_timeout = subtask_timeout
        return td


class TestGuiApplicationLogicWithGUI(DatabaseFixture, LogTestCase):
    def setUp(self):
        DatabaseFixture.setUp(self)
        LogTestCase.setUp(self)
        self.client = Client.__new__(Client)
        from threading import Lock
        self.client.lock = Lock()
        self.client.task_tester = None
        self.logic = GuiApplicationLogic()
        self.app = Gui(self.logic, AppMainWindow)

    def tearDown(self):
        self.app.app.exit(0)
        self.app.app.deleteLater()
        LogTestCase.tearDown(self)
        DatabaseFixture.tearDown(self)

    def test_updating_config_dialog(self):
        logic = self.logic
        app = self.app
        logic.client = Mock()
        logic.register_gui(app.get_main_window(),
                           MainWindowCustomizer)

        logic.lock_config(True)

        self.assertFalse(logic.customizer.gui.ui.settingsOkButton.isEnabled())
        self.assertFalse(
            logic.customizer.gui.ui.settingsCancelButton.isEnabled())

        logic.lock_config(True)
        logic.lock_config(False)
        logic.lock_config(False)

        self.assertTrue(logic.customizer.gui.ui.settingsOkButton.isEnabled())
        self.assertTrue(logic.customizer.gui.ui.settingsCancelButton.isEnabled(
        ))

    def test_main_window(self):
        self.app.main_window.ui.taskTableWidget.setColumnWidth = Mock()
        self.app.main_window.show()

        n = self.app.main_window.ui.taskTableWidget.columnCount()

        set_width = self.app.main_window.ui.taskTableWidget.setColumnWidth
        set_width.assert_has_calls([call(i, ANY) for i in range(0, n)])

    def test_update_peers_view(self):
        logic = self.logic
        gui = self.app
        logic.customizer = MainWindowCustomizer(gui.main_window, logic)
        logic.customizer.new_task_dialog_customizer = Mock()
        peer = Mock()
        peer.ip_port = ("10.10.10.10", 1031)
        peer.remote_pubkey = "KEYID"
        peer2 = Mock()
        peer2.ip_port = ("10.10.10.20", 1034)
        peer2.remote_pubkey = "KEYID2"
        logic._update_peers_view([DictSerializer.dump(peer),
                                  DictSerializer.dump(peer2)])
        table = logic.customizer.gui.ui.connectedPeersTable
        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(table.item(0, 0).text(), "10.10.10.10")
        self.assertEqual(table.item(0, 1).text(), "1031")
        self.assertEqual(table.item(0, 2).text(), "4b45594944")
        self.assertEqual(table.item(1, 0).text(), "10.10.10.20")
        self.assertEqual(table.item(1, 1).text(), "1034")
        self.assertEqual(table.item(1, 2).text(), "4b4559494432")

    def test_change_verification_options(self):
        logic = self.logic
        logic.client = Mock()
        logic.client.datadir = self.path
        self.logic.customizer = MainWindowCustomizer(self.app.main_window,
                                                     self.logic)
        prev_y = logic.customizer.gui.ui.verificationSizeYSpinBox.maximum()
        logic.change_verification_option(size_x_max=914)
        self.assertEqual(
            logic.customizer.gui.ui.verificationSizeXSpinBox.maximum(), 914)
        self.assertEqual(
            logic.customizer.gui.ui.verificationSizeYSpinBox.maximum(), prev_y)
        logic.change_verification_option(size_y_max=123)
        self.assertEqual(
            logic.customizer.gui.ui.verificationSizeXSpinBox.maximum(), 914)
        self.assertEqual(
            logic.customizer.gui.ui.verificationSizeYSpinBox.maximum(), 123)
        logic.change_verification_option(size_y_max=3190, size_x_max=134)
        self.assertEqual(
            logic.customizer.gui.ui.verificationSizeXSpinBox.maximum(), 134)
        self.assertEqual(
            logic.customizer.gui.ui.verificationSizeYSpinBox.maximum(), 3190)

    @ci_skip
    @patch('PyQt5.QtWidgets.QMessageBox')
    def test_messages(self, msg_box):
        msg_box.return_value = msg_box
        logic = self.logic
        self.logic.datadir = self.path
        logic.customizer = MainWindowCustomizer(self.app.main_window, logic)
        logic.customizer.show_error_window = Mock()
        logic.customizer.show_warning_window = Mock()
        logic.customizer.current_task_highlighted = Mock()
        logic.client = Mock()
        self.logic.dir_manager = DirManager(self.path)
        register_task_types(logic)

        rts = TaskDesc()
        self.assertIsInstance(rts, TaskDesc)
        f = self.additional_dir_content([3])
        rts.definition.task_type = "Blender"
        rts.definition.output_file = f[0]
        rts.definition.main_program_file = f[1]
        rts.definition.main_scene_file = f[2]
        self.assertTrue(logic._validate_task_state(rts))
        m = Mock()

        broken_benchmark = BlenderBenchmark()
        broken_benchmark.task_definition.main_program_file = 'Bździągwa'
        logic.customizer.show_error_window = Mock()
        logic.run_benchmark(broken_benchmark, m, m)
        logic.progress_dialog.close()
        if logic.br.tt:
            logic.br.tt.join()
        logic.customizer.show_error_window.assert_called_with(
            "Main program file does not exist: Bździągwa")

        broken_benchmark = BlenderBenchmark()
        broken_benchmark.task_definition.output_file = '/x/y/Bździągwa'
        logic.run_benchmark(broken_benchmark, m, m)
        logic.progress_dialog.close()
        if logic.br.tt:
            logic.br.tt.join()
        logic.customizer.show_error_window.assert_called_with(
            "Cannot open output file: /x/y/Bździągwa")

        broken_benchmark = BlenderBenchmark()
        broken_benchmark.task_definition.main_scene_file = "NOT EXISTING"
        output_file = os.path.join(self.path, str(uuid.uuid4()))
        broken_benchmark.task_definition.output_file = output_file
        logic.run_benchmark(broken_benchmark, m, m)
        logic.progress_dialog.close()
        if logic.br.tt:
            logic.br.tt.join()
        logic.customizer.show_error_window.assert_called_with(
            "Main scene file NOT EXISTING is not properly set")

        logic.test_task_computation_error("Bździągwa")
        text = logic.progress_dialog_customizer.gui.ui.message.text()
        assert text == "Task test computation failure. Bździągwa"
        logic.test_task_computation_error("500 server error")
        text = logic.progress_dialog_customizer.gui.ui.message.text()
        assert text == "Task test computation failure. [500 server error] " \
            "There is a chance that you RAM limit is too low. " \
            "Consider increasing max memory usage"
        logic.test_task_computation_error(None)
        text = logic.progress_dialog_customizer.gui.ui.message.text()
        assert text == "Task test computation failure. "
        logic.test_task_computation_success([], 10000, 1021, {})
        text = logic.progress_dialog_customizer.gui.ui.message.text()
        assert text.startswith("Task tested successfully")
        logic.test_task_computation_success([], 10000, 1021,
                                            {"warnings": "Warning message"})
        text = logic.progress_dialog_customizer.gui.ui.message.text()
        assert text.startswith("Task tested successfully")
        logic.customizer.show_warning_window.assert_called_with(
            "Warning message")

        rts.definition = BlenderBenchmark().task_definition
        rts.definition.output_file = 1342
        self.assertFalse(logic._validate_task_state(rts))

        self.assertEqual(logic._format_stats_message(("STAT1", 2424)),
                         "Session: STAT1; All time: 2424")
        self.assertEqual(logic._format_stats_message(["STAT1"]), "Error")
        self.assertEqual(logic._format_stats_message(13131), "Error")

        ts = TaskDesc()
        ts.definition.task_type = "Blender"
        ts.definition.main_program_file = "nonexisting"
        self.assertFalse(logic._validate_task_state(ts))
        logic.customizer.show_error_window.assert_called_with(
            "Main program file does not exist: nonexisting")

        with self.assertLogs(logger, level="WARNING"):
            logic.set_current_task_type("unknown task")

        def query_task_state(*_):
            deferred = Deferred()
            deferred.callback(True)
            return deferred

        logic.client.query_task_state = query_task_state
        with self.assertLogs(logger, level="WARNING"):
            logic.task_status_changed("unknown id")

        task_type = Mock()
        task_type.name = "NAME1"
        logic.register_new_task_type(task_type)
        with self.assertLogs(int_logger, level="ERROR"):
            logic.register_new_task_type(task_type)

        logic.register_new_test_task_type(task_type)
        with self.assertRaises(RuntimeError):
            logic.register_new_test_task_type(task_type)

    def test_test_task_status(self):

        def reset():
            self.logic.test_task_started = Mock()
            self.logic.test_task_computation_success = Mock()
            self.logic.test_task_computation_error = Mock()

        args = ['first', 'second']

        reset()

        self.logic.test_task_status(TaskTestStatus.started, *args)
        self.logic.test_task_started.assert_called_with(*args)
        assert not self.logic.test_task_computation_success.called
        assert not self.logic.test_task_computation_error.called

        reset()

        self.logic.test_task_status(TaskTestStatus.success, *args)
        self.logic.test_task_computation_success.assert_called_with(*args)
        assert not self.logic.test_task_started.called
        assert not self.logic.test_task_computation_error.called

        reset()

        self.logic.test_task_status(TaskTestStatus.started, *args)
        self.logic.test_task_started.assert_called_with(*args)
        assert not self.logic.test_task_computation_success.called
        assert not self.logic.test_task_computation_error.called

        reset()

        self.logic.test_task_status("test")
        assert not self.logic.test_task_started.called
        assert not self.logic.test_task_computation_success.called
        assert not self.logic.test_task_computation_error.called


def mock_async_run(req):
    return req.method(*req.args, **req.kwargs)


def mock_tester_run(self):
    LocalComputer.run(self)
    self.tt.join()


@patch('devp2p.app.BaseApp.start')
@patch('golem.client.TaskServer.start_accepting')
@patch('golem.client.async_run', side_effect=mock_async_run)
@patch.object(golem.client.TaskTester, 'run', mock_tester_run)
class TestApplicationLogicTestTask(TestDirFixtureWithReactor):

    def setUp(self):
        TestDirFixtureWithReactor.setUp(self)
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False,
                             use_docker_machine_manager=False,
                             use_monitor=False)
        self.client.connect()
        self.logic = GuiApplicationLogic()
        self.app = Gui(self.logic, AppMainWindow)

    def tearDown(self):
        self.client.quit()
        self.app.app.exit(0)
        self.app.app.deleteLater()
        TestDirFixtureWithReactor.tearDown(self)

    @patch('gui.view.dialog.QDialogPlus.enable_close',
           side_effect=lambda *_: True)
    @patch('gui.view.dialog.QDialogPlus.show')
    def test_run_test_task(self, *_):
        logic = self.logic
        gui = self.app

        rpc_session = MockRPCSession(self.client, CORE_METHOD_MAP)
        rpc_client = rpc.session.Client(rpc_session, CORE_METHOD_MAP)
        rpc_publisher = MockRPCPublisher()

        logic.root_path = self.path
        logic.client = rpc_client

        self.client.datadir = logic.root_path
        self.client.rpc_publisher = rpc_publisher
        self.client.start()
        self.client.task_tester = None

        task_type = Mock()
        ttb = TTaskBuilder(self.path)
        task_type.task_builder_type.return_value = ttb
        self.client.task_server.task_manager.task_types["testtask"] = task_type

        logic.customizer = MainWindowCustomizer(gui.main_window, logic)
        logic.customizer.new_task_dialog_customizer = Mock()
        logic.customizer.show_warning_window = Mock()

        ts = TaskDesc()
        files = self.additional_dir_content([3])

        ts.definition.total_subtasks = 1
        ts.definition.main_program_file = files[0]
        ts.definition.task_type = "TESTTASK"
        ts.definition.output_file = files[1]
        ts.definition.main_scene_file = files[2]
        ts.definition.options.use_frames = False

        rpc_publisher.reset()
        logic.run_test_task(ts.definition)
        logic.progress_dialog.close()
        logic.test_task_started(True)
        e = logic.progress_dialog_customizer.gui.ui.abortButton.isEnabled()
        self.assertTrue(e)
        self.assertTrue(rpc_publisher.success)

        ttb.src_code = "import time\ntime.sleep(0.1)\n" \
                       "output = {'data': n, 'result_type': 0}"
        rpc_publisher.reset()
        logic.run_test_task(ts.definition)
        logic.progress_dialog.close()
        self.assertTrue(rpc_publisher.success)

        # since PythonTestVM does not support end_comp() method,
        # this is only a smoke test instead of actual test
        ttb.src_code = "import time\ntime.sleep(0.1)\n" \
                       "output = {'data': n, 'result_type': 0}"
        rpc_publisher.reset()
        logic.run_test_task(ts.definition)
        logic.progress_dialog.close()
        logic.abort_test_task()

        ttb.src_code = "raise Exception('some error')"
        rpc_publisher.reset()
        logic.run_test_task(ts.definition)
        logic.progress_dialog.close()
        self.assertFalse(rpc_publisher.success)

        rpc_publisher.reset()
        logic.run_test_task(ts.definition)
        logic.progress_dialog.close()
        self.assertFalse(rpc_publisher.success)

        ctr = logic.customizer.new_task_dialog_customizer
        prev_call_count = ctr.task_settings_changed.call_count
        logic.task_settings_changed()
        self.assertGreater(ctr.task_settings_changed.call_count,
                           prev_call_count)

        logic.tasks["xyz"] = ts
        logic.clone_task("xyz")

        self.assertEqual(
            logic.customizer.new_task_dialog_customizer.
                load_task_definition.call_args[0][0], ts.definition)

        ttb = TTaskBuilder(self.path, TTaskWithDef)
        self.client.task_server.task_manager.task_types["testtask"] = ttb

        assert logic.run_test_task(ts.definition)
        assert not logic.run_test_task(None)
