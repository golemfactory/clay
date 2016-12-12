import os
import time

import golem
from apps.core.task.gnrtaskstate import GNRTaskState
from apps.rendering.gui.controller.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from ethereum.utils import denoms
from golem.client import Client
from golem.core.simpleserializer import DictSerializer
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.task.taskbase import TaskBuilder, Task, ComputeTaskDef, TaskHeader
from golem.testutils import DatabaseFixture
from golem.tools.assertlogs import LogTestCase
from gui.application import GNRGui
from gui.applicationlogic import GNRApplicationLogic, logger
from gui.view.appmainwindow import AppMainWindow
from mock import Mock, ANY, call
from twisted.internet.defer import Deferred


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
        print "test_task_started {}".format(args)
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

        rpc_publisher.reset()
        logic.run_test_task(ts)
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
