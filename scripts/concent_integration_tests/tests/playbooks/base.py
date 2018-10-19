from pathlib import Path
import re
import sys
import tempfile
import time
import traceback
import typing

from ethereum.utils import denoms

from twisted.internet import reactor, task
from twisted.internet.error import ReactorNotRunning
from twisted.internet import _sslverify  # pylint: disable=protected-access

from scripts.concent_integration_tests.rpc.client import (
    call_requestor, call_provider
)
from scripts.concent_integration_tests import helpers, tasks

_sslverify.platformTrust = lambda: None


class NodeTestPlaybook:
    INTERVAL = 1

    start_time = None

    _loop = None

    provider_node_script: typing.Optional[str] = None
    requestor_node_script: typing.Optional[str] = None
    provider_node = None
    requestor_node = None
    provider_output_queue = None
    requestor_output_queue = None

    provider_port = None

    exit_code = None
    current_step = 0
    provider_key = None
    requestor_key = None
    known_tasks = None
    task_id = None
    started = False
    task_in_creation = False
    output_path = None
    subtasks = None

    task_package = None
    task_settings = 'default'

    @property
    def output_extension(self):
        settings = tasks.get_settings(self.task_settings)
        return settings.get('options').get('format')

    @property
    def current_step_method(self):
        try:
            return self.steps[self.current_step]
        except IndexError:
            return None

    @property
    def current_step_name(self) -> str:
        method = self.current_step_method
        return method.__name__ if method else ''

    @property
    def time_elapsed(self):
        return time.time() - self.start_time

    def fail(self, msg=None):
        print(msg or "Test run failed after {} seconds on step {}: {}".format(
                self.time_elapsed, self.current_step, self.current_step_name))
        self.stop(1)

    def success(self):
        print("Test run completed in {} seconds after {} steps.".format(
            self.time_elapsed, self.current_step + 1, ))
        self.stop(0)

    def next(self):
        self.current_step += 1

    def print_result(self, result):
        print("Result: {}".format(result))

    def print_error(self, error):
        print("Error: {}".format(error))

    def _wait_gnt_eth(self, role, result):
        gnt_balance = int(result.get('gnt')) / denoms.ether
        gntb_balance = int(result.get('av_gnt')) / denoms.ether
        eth_balance = int(result.get('eth')) / denoms.ether
        if gnt_balance > 0 and eth_balance > 0 and gntb_balance > 0:
            print("{} has {} GNT ({} GNTB) and {} ETH.".format(
                role.capitalize(), gnt_balance, gntb_balance, eth_balance))
            self.next()

        else:
            print("Waiting for {} GNT/GNTB/ETH ({}/{}/{})".format(
                role.capitalize(), gnt_balance, gntb_balance, eth_balance))
            time.sleep(15)

    def step_wait_provider_gnt(self):
        def on_success(result):
            return self._wait_gnt_eth('provider', result)

        call_provider('pay.balance', on_success=on_success)

    def step_wait_requestor_gnt(self):
        def on_success(result):
            return self._wait_gnt_eth('requestor', result)

        call_requestor('pay.balance', on_success=on_success)

    def step_get_provider_key(self):
        def on_success(result):
            print("Provider key", result)
            self.provider_key = result
            self.next()

        def on_error(_):
            print("Waiting for the Provider node...")
            time.sleep(3)

        call_provider('net.ident.key',
                      on_success=on_success, on_error=on_error)

    def step_get_requestor_key(self):
        def on_success(result):
            print("Requestor key", result)
            self.requestor_key = result
            self.next()

        def on_error(result):
            print("Waiting for the Requestor node...")
            time.sleep(3)

        call_requestor('net.ident.key',
                       on_success=on_success, on_error=on_error)

    def step_get_provider_network_info(self):
        def on_success(result):
            if result.get('listening') and result.get('port_statuses'):
                self.provider_port = list(result.get('port_statuses').keys())[0]
                print("Provider's port: {}".format(self.provider_port))
                self.next()
            else:
                print("Waiting for Provider's network info...")
                time.sleep(3)

        call_provider('net.status',
                      on_success=on_success, on_error=self.print_error)

    def step_ensure_requestor_network(self):
        def on_success(result):
            if result.get('listening') and result.get('port_statuses'):
                requestor_port = list(result.get('port_statuses').keys())[0]
                print("Requestor's port: {}".format(requestor_port))
                self.next()
            else:
                print("Waiting for Requestor's network info...")
                time.sleep(3)

        call_requestor('net.status',
                      on_success=on_success, on_error=self.print_error)


    def step_connect_nodes(self):
        def on_success(result):
            print("Peer connection initialized.")
            self.next()
        call_requestor('net.peer.connect',
                       ("localhost", self.provider_port, ),
                       on_success=on_success)

    def step_verify_peer_connection(self):
        def on_success(result):
            if len(result) > 1:
                print("Too many peers")
                self.fail()
                return
            elif len(result) == 1:
                peer = result[0]
                if peer['key_id'] != self.provider_key:
                    print("Connected peer: {} != provider peer: {}",
                          peer.key, self.provider_key)
                    self.fail()
                    return

                print("Requestor connected with provider.")
                self.next()
            else:
                print("Waiting for nodes to sync...")

        call_requestor('net.peers.connected',
                       on_success=on_success, on_error=self.print_error)

    def step_get_known_tasks(self):
        def on_success(result):
            self.known_tasks = set(map(lambda r: r['id'], result))
            print("Got current tasks list from the requestor.")
            self.next()

        call_requestor('comp.tasks',
                       on_success=on_success, on_error=self.print_error)

    def step_create_task(self):
        self.output_path = tempfile.mkdtemp()
        print("Output path: {}".format(self.output_path))
        task_dict = helpers.construct_test_task(
            task_package_name=self.task_package,
            output_path=self.output_path,
            task_settings=self.task_settings,
        )

        def on_success(result):
            if result[0]:
                print("Created task.")
                self.next()
            else:
                msg = result[1]
                if re.match('Not enough GNT', msg):
                    print("Waiting for Requestor's GNTB...")
                    time.sleep(30)
                    self.task_in_creation = False
                else:
                    print("Failed to create task {}".format(msg))
                    self.fail()

        if not self.task_in_creation:
            self.task_in_creation = True
            call_requestor('comp.task.create', task_dict,
                           on_success=on_success,
                           on_error=self.print_error)

    def step_get_task_id(self):

        def on_success(result):
            tasks = set(map(lambda r: r['id'], result))
            new_tasks = tasks - self.known_tasks
            if len(new_tasks) != 1:
                print("Cannot find the new task ({})".format(new_tasks))
                time.sleep(30)
            else:
                self.task_id = list(new_tasks)[0]
                print("Task id: {}".format(self.task_id))
                self.next()

        call_requestor('comp.tasks',
                       on_success=on_success, on_error=self.print_error)

    def step_get_task_status(self):
        def on_success(result):
            print("Task status: {}".format(result['status']))
            self.next()

        call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    def step_wait_task_finished(self):
        def on_success(result):
            if result['status'] == 'Finished':
                print("Task finished.")
                self.next()
            else:
                print("{} ... ".format(result['status']))
                time.sleep(10)

        call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    def step_verify_output(self):
        settings = tasks.get_settings(self.task_settings)
        output_file = self.output_path + '/' + \
            settings.get('name') + '.' + self.output_extension
        print("Verifying the output file: {}".format(output_file))
        if Path(output_file).is_file():
            print("Output present :)")
            self.next()
        else:
            print("Failed to find the output.")
            self.fail()

    def step_get_subtasks(self):
        def on_success(result):
            self.subtasks = [
                s.get('subtask_id')
                for s in result
                if s.get('status') == 'Finished'
            ]
            if not self.subtasks:
                self.fail("No subtasks found???")
            self.next()

        call_requestor('comp.task.subtasks', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    def step_verify_provider_income(self):
        def on_success(result):
            payments = [
                p.get('subtask')
                for p in result
                if p.get('payer') == self.requestor_key
            ]
            unpaid = set(self.subtasks) - set(payments)
            if unpaid:
                print("Found subtasks with no matching payments: %s", unpaid)
                self.fail()

            print("All subtasks accounted for.")
            self.success()

        call_provider(
            'pay.incomes', on_success=on_success, on_error=self.print_error)

    steps: typing.Tuple = (
        step_get_provider_key,
        step_get_requestor_key,
        step_get_provider_network_info,
        step_ensure_requestor_network,
        step_connect_nodes,
        step_verify_peer_connection,
        step_wait_provider_gnt,
        step_wait_requestor_gnt,
        step_get_known_tasks,
        step_create_task,
        step_get_task_id,
        step_get_task_status,
        step_wait_task_finished,
        step_verify_output,
        step_get_subtasks,
        step_verify_provider_income,
    )

    def start_nodes(self):
        self.provider_node = helpers.run_golem_node(
            self.provider_node_script
        )
        self.requestor_node = helpers.run_golem_node(
            self.requestor_node_script
        )

        self.provider_output_queue = helpers.get_output_queue(
            self.provider_node)
        self.requestor_output_queue = helpers.get_output_queue(
            self.requestor_node)
        self.started = True

    def stop_nodes(self):
        helpers.gracefully_shutdown(self.provider_node, 'Provider')
        helpers.gracefully_shutdown(self.requestor_node, 'Requestor')
        self.started = False

    def run(self):
        try:
            method = self.current_step_method
            if callable(method):
                method(self)
            else:
                self.fail("Ran out of steps after step {}".format(
                    self.current_step))
                return
        except Exception as e:  # noqa pylint:disable=too-broad-exception
            e, msg, tb = sys.exc_info()
            print("Exception {}: {} on step {}: {}".format(
                e.__name__, msg, self.current_step, self.current_step_name))
            traceback.print_tb(tb)
            self.fail()
            return

        if self.started:
            provider_exit = self.provider_node.poll()
            requestor_exit = self.requestor_node.poll()
            helpers.report_termination(provider_exit, "Provider")
            helpers.report_termination(requestor_exit, "Requestor")
            if provider_exit is not None and requestor_exit is not None:
                self.fail()

    def __init__(self, task_package: str='test_task_1', **kwargs) -> None:
        if not self.provider_node_script or not self.requestor_node_script:
            raise NotImplementedError(
                "Provider and Requestor scripts need to be set")

        if task_package:
            self.task_package = task_package

        for attr, val in kwargs.items():
            setattr(self, attr, val)

        self.start_nodes()
        self.started = True

    @classmethod
    def start(cls, *args, **kwargs):
        playbook = cls(*args, **kwargs)
        playbook.start_time = time.time()
        playbook._loop = task.LoopingCall(playbook.run)
        d = playbook._loop.start(cls.INTERVAL, False)
        d.addErrback(lambda x: print(x))

        reactor.addSystemEventTrigger(
            'before', 'shutdown', lambda: playbook.stop(2))
        reactor.run()

        return playbook

    def stop(self, exit_code):
        if not self.started:
            return

        self.started = False
        try:
            reactor.stop()
        except ReactorNotRunning:
            pass

        self.stop_nodes()
        self.exit_code = exit_code

