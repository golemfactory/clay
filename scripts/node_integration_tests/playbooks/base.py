from pathlib import Path
import re
import sys
import tempfile
import time
import traceback
import typing

from twisted.internet import reactor, task
from twisted.internet.error import ReactorNotRunning
from twisted.internet import _sslverify  # pylint: disable=protected-access

from scripts.node_integration_tests.rpc.client import RPCClient
from scripts.node_integration_tests import helpers, tasks

from scripts.node_integration_tests.params import (
    REQUESTOR_RPC_PORT, PROVIDER_RPC_PORT
)


from golem.rpc.cert import CertificateError

_sslverify.platformTrust = lambda: None


class NodeTestPlaybook:
    INTERVAL = 1

    start_time = None

    _loop = None

    provider_datadir = None
    requestor_datadir = None
    provider_node_script: typing.Optional[str] = None
    requestor_node_script: typing.Optional[str] = None
    provider_enabled = True
    requestor_enabled = True

    nodes_root: typing.Optional[Path] = None
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
    nodes_started = False
    task_in_creation = False
    output_path = None
    subtasks = None

    task_package = None
    task_settings = 'default'
    task_dict = None

    reconnect_attempts_left = 7
    reconnect_countdown_initial = 10
    reconnect_countdown = None

    playbook_description = 'Runs a golem node integration test'

    node_restart_count = 0

    dump_output_on_fail = False

    @property
    def task_settings_dict(self) -> dict:
        return tasks.get_settings(self.task_settings)

    @property
    def output_extension(self):
        return self.task_settings_dict.get('options', {}).get('format')

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

        if self.dump_output_on_fail:
            helpers.print_output(self.provider_output_queue, 'PROVIDER ')
            helpers.print_output(self.requestor_output_queue, 'REQUESTOR ')

        self.stop(1)

    def success(self):
        print("Test run completed in {} seconds after {} steps.".format(
            self.time_elapsed, self.current_step + 1, ))
        self.stop(0)

    def next(self):
        self.current_step += 1

    def previous(self):
        assert (self.current_step > 0), "Cannot move back past step 0"
        self.current_step -= 1

    def print_result(self, result):
        print("Result: {}".format(result))

    def print_error(self, error):
        print("Error: {}".format(error))

    def _wait_gnt_eth(self, role, result):
        gnt_balance = helpers.to_ether(result.get('gnt'))
        gntb_balance = helpers.to_ether(result.get('av_gnt'))
        eth_balance = helpers.to_ether(result.get('eth'))
        if gnt_balance > 0 and eth_balance > 0 and gntb_balance > 0:
            print("{} has {} total GNT ({} GNTB) and {} ETH.".format(
                role.capitalize(), gnt_balance, gntb_balance, eth_balance))
            self.next()

        else:
            print("Waiting for {} GNT(B)/converted GNTB/ETH ({}/{}/{})".format(
                role.capitalize(), gnt_balance, gntb_balance, eth_balance))
            time.sleep(15)

    def step_wait_provider_gnt(self):
        def on_success(result):
            return self._wait_gnt_eth('provider', result)

        return self.call_provider('pay.balance', on_success=on_success)

    def step_wait_requestor_gnt(self):
        def on_success(result):
            return self._wait_gnt_eth('requestor', result)

        return self.call_requestor('pay.balance', on_success=on_success)

    def step_get_provider_key(self):
        def on_success(result):
            print("Provider key", result)
            self.provider_key = result
            self.next()

        def on_error(_):
            print("Waiting for the Provider node...")
            time.sleep(3)

        return self.call_provider('net.ident.key',
                             on_success=on_success, on_error=on_error)

    def step_get_requestor_key(self):
        def on_success(result):
            print("Requestor key", result)
            self.requestor_key = result
            self.next()

        def on_error(result):
            print("Waiting for the Requestor node...")
            time.sleep(3)

        return self.call_requestor('net.ident.key',
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

        return self.call_provider('net.status',
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

        return self.call_requestor('net.status',
                              on_success=on_success, on_error=self.print_error)

    def step_connect_nodes(self):
        def on_success(result):
            print("Peer connection initialized.")
            self.reconnect_countdown = self.reconnect_countdown_initial
            self.next()
        return self.call_requestor('net.peer.connect',
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
                if self.reconnect_countdown <= 0:
                    if self.reconnect_attempts_left > 0:
                        self.reconnect_attempts_left -= 1
                        print("Retrying peer connection.")
                        self.previous()
                        return
                    else:
                        self.fail("Could not sync nodes despite trying hard.")
                        return
                else:
                    self.reconnect_countdown -= 1
                    print("Waiting for nodes to sync...")
                    time.sleep(10)

        return self.call_requestor('net.peers.connected',
                              on_success=on_success, on_error=self.print_error)

    def step_get_known_tasks(self):
        def on_success(result):
            self.known_tasks = set(map(lambda r: r['id'], result))
            print("Got current tasks list from the requestor.")
            self.next()

        return self.call_requestor('comp.tasks',
                              on_success=on_success, on_error=self.print_error)

    def step_create_task(self):
        print("Output path: {}".format(self.output_path))
        print("Task dict: {}".format(self.task_dict))

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
            return self.call_requestor('comp.task.create', self.task_dict,
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

        return self.call_requestor('comp.tasks',
                              on_success=on_success, on_error=self.print_error)

    def step_get_task_status(self):
        def on_success(result):
            print("Task status: {}".format(result['status']))
            self.next()

        return self.call_requestor('comp.task', self.task_id,
                              on_success=on_success, on_error=self.print_error)

    def step_wait_task_finished(self):
        def on_success(result):
            if result['status'] == 'Finished':
                print("Task finished.")
                self.next()
            elif result['status'] == 'Timeout':
                self.fail("Task timed out :( ... ")
            else:
                print("{} ... ".format(result['status']))
                time.sleep(10)

        return self.call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    def step_verify_output(self):
        settings = self.task_settings_dict
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

        return self.call_requestor('comp.task.subtasks', self.task_id,
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
                print("Found subtasks with no matching payments: %s" % unpaid)
                self.fail()
                return

            print("All subtasks accounted for.")
            self.success()

        return self.call_provider(
            'pay.incomes', on_success=on_success, on_error=self.print_error)

    def step_stop_nodes(self):
        if self.nodes_started:
            print("Stopping nodes")
            self.stop_nodes()

        time.sleep(10)
        provider_exit = self.provider_node.poll()
        requestor_exit = self.requestor_node.poll()
        if provider_exit is not None and requestor_exit is not None:
            if provider_exit or requestor_exit:
                print(
                    "Abnormal termination provider: %s, requestor: %s",
                    provider_exit,
                    requestor_exit,
                )
                self.fail()
            else:
                print("Stopped nodes")
                self.next()
        else:
            print("...")

    def step_restart_nodes(self):
        print("Starting nodes again")
        self.node_restart_count += 1

        # replace the the nodes with different versions
        if self.provider_enabled:
            provider_replacement_script = getattr(
                self,
                'provider_node_script_%s' % (self.node_restart_count + 1),
                None,
            )
            if provider_replacement_script:
                self.provider_node_script = provider_replacement_script

        if self.requestor_enabled:
            requestor_replacement_script = getattr(
                self,
                'requestor_node_script_%s' % (self.node_restart_count + 1),
                None,
            )
            if requestor_replacement_script:
                self.requestor_node_script = requestor_replacement_script

        self.task_in_creation = False
        time.sleep(60)

        self.start_nodes()
        print("Nodes restarted")
        self.next()

    initial_steps: typing.Tuple = (
        step_get_provider_key,
        step_get_requestor_key,
        step_get_provider_network_info,
        step_ensure_requestor_network,
        step_connect_nodes,
        step_verify_peer_connection,
        step_wait_provider_gnt,
        step_wait_requestor_gnt,
        step_get_known_tasks,
    )

    steps: typing.Tuple = initial_steps + (
        step_create_task,
        step_get_task_id,
        step_get_task_status,
        step_wait_task_finished,
        step_verify_output,
        step_get_subtasks,
        step_verify_provider_income,
    )

    @staticmethod
    def _call_rpc(method, *args, port, datadir, on_success, on_error, **kwargs):
        try:
            client = RPCClient(
                host='localhost',
                port=port,
                datadir=datadir,
            )
        except CertificateError as e:
            on_error(e)
            return

        return client.call(method, *args,
                           on_success=on_success,
                           on_error=on_error,
                           **kwargs)

    def call_requestor(self, method, *args,
                       on_success=lambda x: print(x),
                       on_error=lambda: None,
                       **kwargs):
        return self._call_rpc(
            method,
            port=int(REQUESTOR_RPC_PORT),
            datadir=self.requestor_datadir,
            *args,
            on_success=on_success,
            on_error=on_error,
            **kwargs,
        )

    def call_provider(self, method, *args,
                      on_success=lambda x: print(x),
                      on_error=None,
                      **kwargs):
        return self._call_rpc(
            method,
            port=int(PROVIDER_RPC_PORT),
            datadir=self.provider_datadir,
            *args,
            on_success=on_success,
            on_error=on_error,
            **kwargs,
        )

    def start_nodes(self):
        print("Provider data directory: %s" % self.provider_datadir)
        print("Requestor data directory: %s" % self.requestor_datadir)

        if self.provider_enabled:
            self.provider_node = helpers.run_golem_node(
                self.provider_node_script,
                '--datadir', self.provider_datadir,
                nodes_root=self.nodes_root,
            )
            self.provider_output_queue = helpers.get_output_queue(
                self.provider_node)

        if self.requestor_enabled:
            self.requestor_node = helpers.run_golem_node(
                self.requestor_node_script,
                '--datadir', self.requestor_datadir,
                nodes_root=self.nodes_root,
            )

            self.requestor_output_queue = helpers.get_output_queue(
                self.requestor_node)

        self.nodes_started = True

    def stop_nodes(self):
        if self.nodes_started:
            if self.provider_node:
                helpers.gracefully_shutdown(self.provider_node, 'Provider')
            if self.requestor_node:
                helpers.gracefully_shutdown(self.requestor_node, 'Requestor')
            self.nodes_started = False

    def run(self):
        if self.nodes_started:
            if self.provider_node:
                provider_exit = self.provider_node.poll()
                helpers.report_termination(provider_exit, "Provider")
                if provider_exit is not None:
                    self.fail("Provider exited abnormally.")

            if self.requestor_node:
                requestor_exit = self.requestor_node.poll()
                helpers.report_termination(requestor_exit, "Requestor")
                if requestor_exit is not None:
                    self.fail("Requestor exited abnormally.")

        try:
            method = self.current_step_method
            if callable(method):
                return method(self)
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

    def __init__(self, **kwargs) -> None:
        if not self.provider_node_script and self.provider_enabled:
            raise NotImplementedError(
                "`provider_node_script` unset and not explicitly disabled.")

        if not self.requestor_node_script and self.requestor_enabled:
            raise NotImplementedError(
                "`requestor_node_script` unset and not explicitly disabled.")

        for attr, val in kwargs.items():
            setattr(self, attr, val)

        self.output_path = tempfile.mkdtemp()
        self.task_dict = helpers.construct_test_task(
            task_package_name=self.task_package,
            output_path=self.output_path,
            task_settings=self.task_settings,
        )

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

