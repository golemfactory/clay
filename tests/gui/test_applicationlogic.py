import os
import time
import uuid

from ethereum.utils import denoms
from mock import Mock, MagicMock, ANY, call
from twisted.internet.defer import Deferred

from apps.core.task.gnrtaskstate import GNRTaskState, GNRTaskDefinition
from apps.rendering.gui.controller.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from golem.client import Client
from golem.rpc.service import RPCServiceInfo, RPCAddress, ServiceHelper, RPCProxyClient
from golem.task.taskbase import TaskBuilder, Task, ComputeTaskDef
from golem.task.taskstate import TaskStatus
from golem.testutils import DatabaseFixture
from golem.tools.assertlogs import LogTestCase
from gui.application import GNRGui
from gui.applicationlogic import GNRApplicationLogic, logger
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


class TTaskBuilder(TaskBuilder):
    def __init__(self, path):
        self.path = path
        self.src_code = "output = {'data': n, 'result_type': 0}"
        self.extra_data = {"n": 421}

    def build(self):
        t = TTask()
        t.header.node_name = "node1"
        t.header.task_id = "xyz"
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
        print "test_task_started {}".format(args)
        self.started = args[0]


class MockDeferred(Deferred):
    def __init__(self, result):
        Deferred.__init__(self)
        self.result = result
        self.called = True


class MockDeferredCallable(MagicMock):
    def __call__(self, *args, **kwargs):
        return MockDeferred(MagicMock())


class MockRPCCallChain(object):
    def __init__(self, parent):
        self.parent = parent
        self.results = []

    def __getattribute__(self, item):
        if item in ['call', 'parent', 'results'] or item.startswith('_'):
            return object.__getattribute__(self, item)
        return self

    def __call__(self, *args, **kwargs):
        self.results.append('value')
        return self

    def call(self):
        return MockDeferred(self.results)


class MockRPCClient(RPCProxyClient):
    def __init__(self, service, path):
        self.methods = ServiceHelper.to_dict(service)

    def call_batch(self, batch):
        return MockDeferred(MagicMock())

    def start_batch(self):
        return MockRPCCallChain(self)

    def wrap(self, name, _):
        def return_deferred(*args, **kwargs):
            return MockDeferred('value')

        return return_deferred


class MockService(object):
    def method_1(self):
        return 1


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


class TestGNRApplicationLogicWithClient(DatabaseFixture, LogTestCase):
    def setUp(self):
        super(TestGNRApplicationLogicWithClient, self).setUp()
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False, use_docker_machine_manager=False,
                             use_monitor=False)

    def tearDown(self):
        self.client.quit()
        super(TestGNRApplicationLogicWithClient, self).tearDown()

    def test_inline_callbacks(self):
        logic = GNRApplicationLogic()
        logic.customizer = Mock()

        golem_client = self.client
        golem_client.task_server = Mock()
        golem_client.p2pservice = Mock()
        golem_client.resource_server = Mock()

        golem_client.task_server.get_task_computer_root.return_value = MockDeferred(self.path)
        golem_client.task_server.task_computer.get_progresses.return_value = {}
        golem_client.p2pservice.peers = {}
        golem_client.p2pservice.get_peers.return_value = {}
        golem_client.resource_server.get_distributed_resource_root.return_value = self.path

        client = MockRPCClient(golem_client, self.path)
        service_info = RPCServiceInfo(MockService(), RPCAddress('127.0.0.1', 10000))

        logic.register_client(client, service_info)
        logic.get_res_dirs()
        logic.check_network_state()
        logic.get_status()
        logic.update_estimated_reputation()
        logic.update_stats()
        logic.get_keys_auth()
        logic.save_task('any', os.path.join(self.path, str(uuid.uuid4())))
        logic.save_task('any', os.path.join(self.path, str(uuid.uuid4()) + ".gt"))
        logic.recount_performance(1)
        logic.get_environments()
        logic.get_payments()
        logic.get_incomes()
        logic.get_key_id()
        logic.get_difficulty()
        logic.load_keys_from_file('invalid')
        logic.save_keys_to_files(os.path.join(self.path, 'invalid_1'), os.path.join(self.path, 'invalid_2'))

        logic.get_cost_for_task_id("unknown task")

    def test_change_description(self):
        logic = GNRApplicationLogic()
        logic.customizer = Mock()
        golem_client = self.client
        client = MockRPCClient(golem_client, self.path)
        service_info = RPCServiceInfo(MockService(), RPCAddress('127.0.0.1', 10000))
        logic.register_client(client, service_info)
        golem_client.change_description("NEW DESC")
        time.sleep(0.5)
        assert golem_client.get_description() == "NEW DESC"

    def test_add_tasks(self):
        logic = GNRApplicationLogic()
        logic.customizer = Mock()
        golem_client = self.client
        client = MockRPCClient(golem_client, self.path)
        service_info = RPCServiceInfo(MockService(), RPCAddress('127.0.0.1', 10000))
        logic.register_client(client, service_info)

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

    @staticmethod
    def _get_task_state(task_id="xyz", full_task_timeout=100, subtask_timeout=50):
        task_state = GNRTaskState()
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

    def test_messages(self):
        logic = GNRApplicationLogic()
        logic.customizer = Mock()
        assert logic._format_stats_message(("STAT1", 2424)) == u"Session: STAT1; All time: 2424"
        assert logic._format_stats_message(["STAT1"]) == u"Error"
        assert logic._format_stats_message(13131) == u"Error"

        ts = GNRTaskState()
        ts.definition.main_program_file = "nonexisting"
        assert not logic._validate_task_state(ts)
        logic.customizer.show_error_window.assert_called_with(u"Main program file does not exist: nonexisting")

        with self.assertLogs(logger, level="WARNING"):
            logic.set_current_task_type("unknown task")

        with self.assertLogs(logger, level="WARNING"):
            logic.task_status_changed("unknown id")

        task_type = Mock()
        task_type.name = "NAME1"
        logic.register_new_task_type(task_type)
        with self.assertRaises(AssertionError):
            logic.register_new_task_type(task_type)

        logic.register_new_test_task_type(task_type)
        with self.assertRaises(AssertionError):
            logic.register_new_test_task_type(task_type)


class TestGNRApplicationLogicWithGUI(DatabaseFixture):
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
                           RenderingMainWindowCustomizer)

        logic.toggle_config_dialog(True)

        assert not logic.customizer.gui.ui.settingsOkButton.isEnabled()
        assert not logic.customizer.gui.ui.settingsCancelButton.isEnabled()

        logic.toggle_config_dialog(True)
        logic.toggle_config_dialog(False)
        logic.toggle_config_dialog(False)

        assert logic.customizer.gui.ui.settingsOkButton.isEnabled()
        assert logic.customizer.gui.ui.settingsCancelButton.isEnabled()

    def test_run_test_task(self):
        logic = self.logic
        gnrgui = self.app

        rpc_client = RPCClient()

        logic.root_path = self.path
        logic.client = self.client
        logic.client.datadir = logic.root_path
        logic.client.rpc_clients = [rpc_client]

        logic.customizer = RenderingMainWindowCustomizer(gnrgui.main_window, logic)
        logic.customizer.new_task_dialog_customizer = Mock()

        ts = Mock()
        files = self.additional_dir_content([1])
        ts.definition.main_program_file = files[0]
        ts.definition.task_type = "TESTTASK"

        task_type = Mock()
        ttb = TTaskBuilder(self.path)
        task_type.task_builder_type.return_value = ttb
        logic.task_types["TESTTASK"] = task_type

        logic.run_test_task(ts)
        logic.test_task_started(True)
        assert logic.progress_dialog_customizer.gui.ui.abortButton.isEnabled()
        time.sleep(0.5)

        assert rpc_client.success

        assert not rpc_client.started
        ttb.src_code = "import time\ntime.sleep(0.1)\noutput = {'data': n, 'result_type': 0}"
        logic.run_test_task(ts)
        time.sleep(1)
        assert rpc_client.success

        # since PythonTestVM does not support end_comp() method,
        # this is only a smoke test instead of actual test
        ttb.src_code = "import time\ntime.sleep(0.1)\noutput = {'data': n, 'result_type': 0}"
        logic.run_test_task(ts)
        assert rpc_client.started
        logic.abort_test_task()
        time.sleep(0.1)
        # assert rpc_client.error

        ttb.src_code = "raise Exception('some error')"
        logic.run_test_task(ts)
        time.sleep(0.5)

        assert rpc_client.error

        logic.run_test_task(ts)
        time.sleep(0.5)

        assert rpc_client.error

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
        logic.customizer = RenderingMainWindowCustomizer(gnrgui.main_window, logic)
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
        logic._update_peers_view([peer, peer2])
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
