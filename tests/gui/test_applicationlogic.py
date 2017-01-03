#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import time
import uuid

from ethereum.utils import denoms
from mock import Mock, ANY, call
from twisted.internet.defer import Deferred

import golem
from golem import rpc
from golem.client import Client
from golem.core.simpleserializer import DictSerializer
from golem.interface.client.logic import logger as int_logger
from golem.resource.dirmanager import DirManager
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.task.taskbase import TaskBuilder, Task, ComputeTaskDef, TaskHeader
from golem.task.taskstate import TaskStatus
from golem.testutils import DatabaseFixture
from golem.tools.assertlogs import LogTestCase

from apps.core.task.gnrtaskstate import TaskDesc, GNRTaskDefinition
from apps.blender.benchmark.benchmark import BlenderBenchmark
from gui.controller.mainwindowcustomizer import MainWindowCustomizer

from gui.application import GNRGui
from gui.applicationlogic import GNRApplicationLogic, logger
from gui.startapp import register_rendering_task_types
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

    def get_output_names(self):
        return ["output1", "output2", "output3"]


class TTaskBuilder(TaskBuilder):

    def __init__(self, path):
        self.path = path
        self.src_code = "output = {'data': n, 'result_type': 0}"
        self.extra_data = {"n": 421}

    def build(self):
        t = TTask()
        t.header = TaskHeader(
            node_name="node1",
            task_id="xyz",
            task_owner_address="127.0.0.1",
            task_owner_port=45000,
            task_owner_key_id="key2",
            environment="test"
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

        for k, v in method_map.iteritems():
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


class MockRPCPublisher(object):

    def __init__(self, success_aliases, error_aliases):
        self.success_aliases = success_aliases
        self.error_aliases = error_aliases
        self.success = None

    def publish(self, alias, *args, **kwargs):

        if alias in self.success_aliases:
            self.success = True
        elif alias in self.error_aliases:
            self.success = False

    def reset(self):
        self.success = None


class TestGNRApplicationLogic(DatabaseFixture):

    def test_root_path(self):
        logic = GNRApplicationLogic()
        self.assertTrue(os.path.isdir(logic.root_path))

    def test_update_payments_view(self):
        logic = GNRApplicationLogic()
        logic.client = Mock()
        logic.customizer = Mock()
        ether = denoms.ether

        balance_deferred = Deferred()
        balance_deferred.result = (3 * ether, 1 * ether, 0.3 * ether)
        balance_deferred.called = True

        logic.client.get_balance.return_value = balance_deferred
        logic.update_payments_view()

        ui = logic.customizer.gui.ui
        ui.localBalanceLabel.setText.assert_called_once_with("3.000000 ETH")
        ui.reservedBalanceLabel.setText.assert_called_once_with("2.000000 ETH")
        ui.availableBalanceLabel.setText.assert_called_once_with("1.000000 ETH")
        ui.depositBalanceLabel.setText.assert_called_once_with("0.300000 ETH")

    def test_start_task(self):
        logic = GNRApplicationLogic()
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


class TestGNRApplicationLogicWithClient(DatabaseFixture, LogTestCase):

    def setUp(self):
        super(TestGNRApplicationLogicWithClient, self).setUp()
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False, use_docker_machine_manager=False,
                             use_monitor=False)

    def tearDown(self):
        self.client.quit()
        super(TestGNRApplicationLogicWithClient, self).tearDown()

    def test_change_description(self):
        logic = GNRApplicationLogic()
        logic.customizer = Mock()

        rpc_session = MockRPCSession(self.client, CORE_METHOD_MAP)
        rpc_client = golem.rpc.session.Client(rpc_session, CORE_METHOD_MAP)

        description = u"New description"

        logic.client = rpc_client
        logic.change_description(description)
        assert self.client.get_description() == description

    def test_add_tasks(self):
        logic = GNRApplicationLogic()
        logic.customizer = Mock()
        td = TestGNRApplicationLogicWithClient._get_task_definition()
        logic.add_task_from_definition(td)
        assert "xyz" in logic.tasks, "Task was not added"
        task_state1 = TestGNRApplicationLogicWithClient._get_task_state()
        task_state2 = TestGNRApplicationLogicWithClient._get_task_state(task_id="abc")
        task_state3 = TestGNRApplicationLogicWithClient._get_task_state(task_id="def")
        logic.add_tasks([task_state1, task_state2, task_state3])
        self.assertEqual(len(logic.tasks), 3, "Incorrect number of tasks")
        assert "xyz" in logic.tasks, "Task was not added"
        assert "abc" in logic.tasks, "Task was not added"
        assert "def" in logic.tasks, "Task was not added"
        self.assertEqual(logic.tasks["xyz"].definition.full_task_timeout, 100, "Wrong task timeout")
        self.assertEqual(logic.tasks["xyz"].definition.subtask_timeout, 50, "Wrong subtask timeout")
        result = logic.add_tasks([])
        self.assertIsNone(result, "Returned value [{}] is not None".format(result))
        result = logic.get_test_tasks()
        self.assertEqual(result, {}, "Returned value is not empty")
        with self.assertLogs(logger):
            logic.change_timeouts("invalid", 10, 10)

        logic.config_changed()

    @staticmethod
    def _get_task_state(task_id="xyz", full_task_timeout=100, subtask_timeout=50):
        task_state = TaskDesc()
        td = TestGNRApplicationLogicWithClient._get_task_definition(task_id=task_id,
                                                                    full_task_timeout=full_task_timeout,
                                                                    subtask_timeout=subtask_timeout)
        task_state.status = TaskStatus.notStarted
        task_state.definition = td
        return task_state

    @staticmethod
    def _get_task_definition(task_id="xyz", full_task_timeout=100, subtask_timeout=50):
        td = GNRTaskDefinition()
        td.task_id = task_id
        td.full_task_timeout = full_task_timeout
        td.subtask_timeout = subtask_timeout
        return td


class TestGNRApplicationLogicWithGUI(DatabaseFixture, LogTestCase):
    def setUp(self):
        super(TestGNRApplicationLogicWithGUI, self).setUp()
        self.client = Client.__new__(Client)
        from threading import Lock
        self.client.lock = Lock()
        self.client.task_tester = None
        self.logic = GNRApplicationLogic()
        self.app = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestGNRApplicationLogicWithGUI, self).tearDown()
        self.app.app.exit(0)
        self.app.app.deleteLater()

    def test_updating_config_dialog(self):
        logic = self.logic
        app = self.app
        logic.client = Mock()
        logic.register_gui(app.get_main_window(),
                           MainWindowCustomizer)

        logic.lock_config(True)

        assert not logic.customizer.gui.ui.settingsOkButton.isEnabled()
        assert not logic.customizer.gui.ui.settingsCancelButton.isEnabled()

        logic.lock_config(True)
        logic.lock_config(False)
        logic.lock_config(False)

        assert logic.customizer.gui.ui.settingsOkButton.isEnabled()
        assert logic.customizer.gui.ui.settingsCancelButton.isEnabled()

    def test_run_test_task(self):
        logic = self.logic
        gnrgui = self.app

        rpc_session = MockRPCSession(self.client, CORE_METHOD_MAP)
        rpc_client = golem.rpc.session.Client(rpc_session, CORE_METHOD_MAP)
        rpc_publisher = MockRPCPublisher(success_aliases=[golem.rpc.mapping.aliases.Task.evt_task_check_success],
                                         error_aliases=[golem.rpc.mapping.aliases.Task.evt_task_check_error])

        logic.root_path = self.path
        logic.client = rpc_client

        self.client.datadir = logic.root_path
        self.client.rpc_publisher = rpc_publisher

        logic.customizer = MainWindowCustomizer(gnrgui.main_window, logic)
        logic.customizer.new_task_dialog_customizer = Mock()
        logic.customizer.show_warning_window = Mock()

        ts = TaskDesc()
        files = self.additional_dir_content([1])
        ts.definition.main_program_file = files[0]
        ts.definition.task_type = "TESTTASK"
        f = self.additional_dir_content([2])
        ts.definition.output_file = f[0]
        ts.definition.main_scene_file = f[1]  # FIXME Remove me

        task_type = Mock()
        ttb = TTaskBuilder(self.path)
        task_type.task_builder_type.return_value = ttb
        logic.task_types["TESTTASK"] = task_type

        rpc_publisher.reset()
        logic.run_test_task(ts)
        logic.test_task_started(True)
        assert logic.progress_dialog_customizer.gui.ui.abortButton.isEnabled()
        time.sleep(0.5)
        assert rpc_publisher.success

        ttb.src_code = "import time\ntime.sleep(0.1)\noutput = {'data': n, 'result_type': 0}"
        rpc_publisher.reset()
        logic.run_test_task(ts)
        time.sleep(0.5)
        assert rpc_publisher.success

        # since PythonTestVM does not support end_comp() method,
        # this is only a smoke test instead of actual test
        ttb.src_code = "import time\ntime.sleep(0.1)\noutput = {'data': n, 'result_type': 0}"
        rpc_publisher.reset()
        logic.run_test_task(ts)
        time.sleep(0.5)
        logic.abort_test_task()

        ttb.src_code = "raise Exception('some error')"
        rpc_publisher.reset()
        logic.run_test_task(ts)
        time.sleep(1)
        assert not rpc_publisher.success

        rpc_publisher.reset()
        logic.run_test_task(ts)
        assert not rpc_publisher.success

        prev_call_count = logic.customizer.new_task_dialog_customizer.task_settings_changed.call_count
        logic.task_settings_changed()
        assert logic.customizer.new_task_dialog_customizer.task_settings_changed.call_count > prev_call_count

        logic.tasks["xyz"] = ts
        logic.clone_task("xyz")

        assert logic.customizer.new_task_dialog_customizer.load_task_definition.call_args[0][0] == ts.definition

    def test_main_window(self):
        self.app.main_window.ui.taskTableWidget.setColumnWidth = Mock()
        self.app.main_window.show()

        n = self.app.main_window.ui.taskTableWidget.columnCount()

        set_width = self.app.main_window.ui.taskTableWidget.setColumnWidth
        set_width.assert_has_calls([call(i, ANY) for i in xrange(0, n)])

    def test_update_peers_view(self):
        logic = self.logic
        gnrgui = self.app
        logic.customizer = MainWindowCustomizer(gnrgui.main_window, logic)
        logic.customizer.new_task_dialog_customizer = Mock()
        peer = Mock()
        peer.address = "10.10.10.10"
        peer.port = 1031
        peer.key_id = "KEYID"
        peer.node_name = "NODE 1"
        peer2 = Mock()
        peer2.address = "10.10.10.20"
        peer2.port = 1034
        peer2.key_id = "KEYID2"
        peer2.node_name = "NODE 2"
        logic._update_peers_view([DictSerializer.dump(peer), DictSerializer.dump(peer2)])
        table = logic.customizer.gui.ui.connectedPeersTable
        assert table.rowCount() == 2
        assert table.item(0, 0).text() == "10.10.10.10"
        assert table.item(1, 0).text() == "10.10.10.20"
        assert table.item(0, 1).text() == "1031"
        assert table.item(1, 1).text() == "1034"
        assert table.item(0, 2).text() == "KEYID"
        assert table.item(1, 2).text() == "KEYID2"
        assert table.item(0, 3).text() == "NODE 1"
        assert table.item(1, 3).text() == "NODE 2"

    def test_change_verification_options(self):
        logic = self.logic
        logic.client = Mock()
        logic.client.datadir = self.path
        self.logic.customizer = MainWindowCustomizer(self.app.main_window, self.logic)
        prev_y = logic.customizer.gui.ui.verificationSizeYSpinBox.maximum()
        logic.change_verification_option(size_x_max=914)
        assert logic.customizer.gui.ui.verificationSizeXSpinBox.maximum() == 914
        assert logic.customizer.gui.ui.verificationSizeYSpinBox.maximum() == prev_y
        logic.change_verification_option(size_y_max=123)
        assert logic.customizer.gui.ui.verificationSizeXSpinBox.maximum() == 914
        assert logic.customizer.gui.ui.verificationSizeYSpinBox.maximum() == 123
        logic.change_verification_option(size_y_max=3190, size_x_max=134)
        assert logic.customizer.gui.ui.verificationSizeXSpinBox.maximum() == 134
        assert logic.customizer.gui.ui.verificationSizeYSpinBox.maximum() == 3190

    def test_messages(self):
        logic = self.logic
        self.logic.datadir = self.path
        logic.customizer = MainWindowCustomizer(self.app.main_window, logic)
        logic.customizer.show_error_window = Mock()
        logic.customizer.show_warning_window =  Mock()
        self.logic.dir_manager = DirManager(self.path)
        register_rendering_task_types(logic)

        rts = TaskDesc()
        assert isinstance(rts, TaskDesc)
        f = self.additional_dir_content([3])
        rts.definition.task_type = "Blender"
        rts.definition.output_file = f[0]
        rts.definition.main_program_file = f[1]
        rts.definition.main_scene_file = f[2]
        assert logic._validate_task_state(rts)
        m = Mock()

        broken_benchmark = BlenderBenchmark()
        broken_benchmark.task_definition.main_program_file = u'Bździągwa'
        logic.customizer.show_error_window = Mock()
        logic.run_benchmark(broken_benchmark, m, m)
        if logic.br.tt:
            logic.br.tt.join()
        logic.customizer.show_error_window.assert_called_with(u"Main program file does not exist: Bździągwa")

        broken_benchmark = BlenderBenchmark()
        broken_benchmark.task_definition.output_file = u'/x/y/Bździągwa'
        logic.run_benchmark(broken_benchmark, m, m)
        if logic.br.tt:
            logic.br.tt.join()
        logic.customizer.show_error_window.assert_called_with(u"Cannot open output file: /x/y/Bździągwa")

        broken_benchmark = BlenderBenchmark()
        broken_benchmark.task_definition.main_scene_file = "NOT EXISTING"
        broken_benchmark.task_definition.output_file = os.path.join(self.path, str(uuid.uuid4()))
        logic.run_benchmark(broken_benchmark, m, m)
        if logic.br.tt:
            logic.br.tt.join()
        logic.customizer.show_error_window.assert_called_with(u"Main scene file NOT EXISTING is not properly set")

        logic.test_task_computation_error(u"Bździągwa")
        logic.progress_dialog_customizer.gui.ui.message.text() == u"Task test computation failure. Bździągwa"
        logic.test_task_computation_error(u"500 server error")
        logic.progress_dialog_customizer.gui.ui.message.text() == \
            u"Task test computation failure. [500 server error] There is a chance that you RAM limit is too low. " \
            u"Consider increasing max memory usage"
        logic.test_task_computation_error(None)
        logic.progress_dialog_customizer.gui.ui.message.text() == u"Task test computation failure. "
        logic.test_task_computation_success([], 10000)
        logic.progress_dialog_customizer.gui.ui.message.text() == u"Task task computation success!"

        rts.definition = BlenderBenchmark().task_definition
        rts.definition.output_file = 1342
        assert not logic._validate_task_state(rts)

        assert logic._format_stats_message(("STAT1", 2424)) == u"Session: STAT1; All time: 2424"
        assert logic._format_stats_message(["STAT1"]) == u"Error"
        assert logic._format_stats_message(13131) == u"Error"

        ts = TaskDesc()
        ts.definition.task_type = "Blender"
        ts.definition.main_program_file = "nonexisting"
        assert not logic._validate_task_state(ts)
        print logic.customizer.show_error_window
        logic.customizer.show_error_window.assert_called_with(u"Main program file does not exist: nonexisting")

        with self.assertLogs(logger, level="WARNING"):
            logic.set_current_task_type("unknown task")

        with self.assertLogs(logger, level="WARNING"):
            logic.task_status_changed("unknown id")

        task_type = Mock()
        task_type.name = "NAME1"
        logic.register_new_task_type(task_type)
        with self.assertLogs(int_logger, level="ERROR"):
            logic.register_new_task_type(task_type)

        logic.register_new_test_task_type(task_type)
        with self.assertRaises(AssertionError):
            logic.register_new_test_task_type(task_type)
