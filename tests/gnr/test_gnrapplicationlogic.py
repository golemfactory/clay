import os
import time
import uuid

from gnr.renderingapplicationlogic import RenderingApplicationLogic
from mock import Mock, MagicMock
from twisted.internet.defer import Deferred

from gnr.application import GNRGui
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnr.gnrapplicationlogic import GNRApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow
from golem.client import Client
from golem.rpc.service import RPCServiceInfo, RPCAddress, ServiceMethodNamesProxy, ServiceHelper
from golem.task.taskbase import TaskBuilder, Task, ComputeTaskDef
from golem.tools.testdirfixture import TestDirFixture


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

    def test_task_computation_success(self, *args, **kwargs):
        self.success = True
        self.error = False

    def test_task_computation_error(self, *args, **kwargs):
        self.success = False
        self.error = True


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


class MockRPCClient(ServiceMethodNamesProxy):
    def __init__(self, service):
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


class TestGNRApplicationLogic(TestDirFixture):

    def test_root_path(self):
        logic = GNRApplicationLogic()
        self.assertTrue(os.path.isdir(logic.root_path))

    def test_run_test_task(self):
        rpc_client = RPCClient()

        logic = GNRApplicationLogic()
        logic.client = Client.__new__(Client)
        logic.client.datadir = logic.root_path
        logic.client.rpc_clients = [rpc_client]

        gnrgui = GNRGui(Mock(), AppMainWindow)

        logic.client.datadir = self.path
        logic.customizer = RenderingMainWindowCustomizer(gnrgui.main_window, logic)
        logic.customizer.new_task_dialog_customizer = Mock()

        ts = Mock()
        files = self.additional_dir_content([1])
        ts.definition.main_program_file = files[0]
        ts.definition.renderer = "TESTTASK"

        task_type = Mock()
        ttb = TTaskBuilder(self.path)
        task_type.task_builder_type.return_value = ttb
        logic.task_types["TESTTASK"] = task_type

        logic.run_test_task(ts)
        time.sleep(0.5)

        assert rpc_client.success

        ttb.src_code = "raise Exception('some error')"
        logic.run_test_task(ts)
        time.sleep(0.5)

        assert rpc_client.error

        ttb.src_code = "print 'hello'"
        logic.run_test_task(ts)
        time.sleep(0.5)

        assert rpc_client.error

        prev_call_count = logic.customizer.new_task_dialog_customizer.task_settings_changed.call_count
        logic.task_settings_changed()
        assert logic.customizer.new_task_dialog_customizer.task_settings_changed.call_count > prev_call_count

        logic.tasks["xyz"] = ts
        logic.clone_task("xyz")

        assert logic.customizer.new_task_dialog_customizer.load_task_definition.call_args[0][0] == ts.definition

        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()

    def test_update_payments_view(self):
        logic = GNRApplicationLogic()
        logic.client = Mock()
        logic.customizer = Mock()
        eth = 10**18

        balance_deferred = Deferred()
        balance_deferred.result = (3 * eth, 1 * eth)
        balance_deferred.called = True

        logic.client.get_balance.return_value = balance_deferred
        logic.update_payments_view()

        ui = logic.customizer.gui.ui
        ui.localBalanceLabel.setText.assert_called_once_with("3.000000 ETH")
        ui.reservedBalanceLabel.setText.assert_called_once_with("2.000000 ETH")
        ui.availableBalanceLabel.setText.assert_called_once_with("1.000000 ETH")

    def test_inline_callbacks(self):

        logic = GNRApplicationLogic()
        logic.customizer = Mock()

        golem_client = Client()
        golem_client.task_server = Mock()
        golem_client.p2pservice = Mock()
        golem_client.resource_server = Mock()

        golem_client.task_server.get_task_computer_root.return_value = MockDeferred(self.path)
        golem_client.task_server.task_computer.get_progresses.return_value = {}
        golem_client.p2pservice.peers = {}
        golem_client.p2pservice.get_peers.return_value = {}
        golem_client.resource_server.get_distributed_resource_root.return_value = self.path

        client = MockRPCClient(golem_client)
        service_info = RPCServiceInfo(MockService(), RPCAddress('127.0.0.1', 10000))

        logic.register_client(client, service_info)
        logic.get_res_dirs()
        logic.check_network_state()
        logic.get_status()
        logic.update_estimated_reputation()
        logic.update_stats()
        logic.get_keys_auth()
        logic.save_task('any', os.path.join(self.path, str(uuid.uuid4())))
        logic.recount_performance(1)
        logic.get_environments()
        logic.get_payments()
        logic.get_incomes()
        logic.get_key_id()
        logic.get_difficulty()
        logic.load_keys_from_file('invalid')
        logic.save_keys_to_files(os.path.join(self.path, 'invalid_1'), os.path.join(self.path, 'invalid_2'))

        golem_client.quit()

    def test_updating_config_dialog(self):
        logic = RenderingApplicationLogic()
        app = GNRGui(logic, AppMainWindow)

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

        app.app.exit(0)
        app.app.deleteLater()
