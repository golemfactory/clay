from functools import partial, wraps
from pathlib import Path
import re
import sys
import tempfile
import time
import traceback
import typing

from bidict import bidict

from twisted.internet import reactor, task
from twisted.internet.error import ReactorNotRunning
from twisted.internet import _sslverify  # pylint: disable=protected-access

from scripts.node_integration_tests.rpc.client import RPCClient
from scripts.node_integration_tests import helpers, tasks

from golem.rpc.cert import CertificateError

from .test_config_base import NodeId

if typing.TYPE_CHECKING:
    from queue import Queue
    from subprocess import Popen
    from .test_config_base import TestConfigBase, NodeConfig


_sslverify.platformTrust = lambda: None


def print_result(result):
    print(f"Result: {result}")


def print_error(error):
    print(f"Error: {error}")


def catch_and_print_exceptions(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except:
            traceback.print_exc()
    return wrapper


class NodeTestPlaybook:
    INTERVAL = 1
    RECONNECT_COUNTDOWN_INITIAL = 10

    def __init__(self, config: 'TestConfigBase') -> None:
        self.config = config

        def setup_datadir(
                node_id: NodeId,
                node_configs:
                'typing.Union[NodeConfig, typing.List[NodeConfig]]') \
                -> None:
            if isinstance(node_configs, list):
                datadir: typing.Optional[str] = None
                for node_config in node_configs:
                    if node_config.datadir is None:
                        if datadir is None:
                            datadir = helpers.mkdatadir(node_id.value)
                        node_config.datadir = datadir
            else:
                if node_configs.datadir is None:
                    node_configs.datadir = helpers.mkdatadir(node_id.value)

        for node_id, node_configs in self.config.nodes.items():
            setup_datadir(node_id, node_configs)

        self.output_path = tempfile.mkdtemp(
            prefix="golem-integration-test-output-")
        helpers.set_task_output_path(self.config.task_dict, self.output_path)

        self.nodes: 'typing.Dict[NodeId, Popen]' = {}
        self.output_queues: 'typing.Dict[NodeId, Queue]' = {}
        self.nodes_ports: typing.Dict[NodeId, int] = {}
        self.nodes_keys: bidict[NodeId, str] = bidict()
        self.nodes_exit_codes: typing.Dict[NodeId, typing.Optional[int]] = {}

        self._loop = task.LoopingCall(self.run)
        self.start_time: float = 0
        self.exit_code = 0
        self.current_step = 0
        self.known_tasks: typing.Optional[typing.Set[str]] = None
        self.task_id: typing.Optional[str] = None
        self.nodes_started = False
        self.task_in_creation = False
        self.subtasks: typing.Dict[NodeId, typing.Set[str]] = {}

        self.reconnect_attempts_left = 7
        self.reconnect_countdown = self.RECONNECT_COUNTDOWN_INITIAL
        self.has_requested_eth: bool = False
        self.retry_counter = 0

        self.start_nodes()
        self.started = True

    @property
    def task_settings_dict(self) -> dict:
        return tasks.get_settings(self.config.task_settings)

    @property
    def output_extension(self):
        return self.task_settings_dict.get('options', {}).get('format')

    @property
    def current_step_method(self):
        return self.steps[self.current_step]

    @property
    def current_step_name(self) -> str:
        step = self.current_step_method
        if isinstance(step, partial):
            kwargs = ", ".join(f"{k}={v}" for k, v in step.keywords.items())
            return step.func.__name__ + '(' + kwargs + ')'
        return step.__name__

    @property
    def time_elapsed(self) -> float:
        return time.time() - self.start_time

    def fail(self, msg: typing.Optional[str] = None):
        print(msg or "Test run failed after {} seconds on step {}: {}".format(
                self.time_elapsed, self.current_step, self.current_step_name))

        for node_id, output_queue in self.output_queues.items():
            if self.config.dump_output_on_fail or (
                    self.config.dump_output_on_crash
                    and self.nodes_exit_codes[node_id] is not None):
                helpers.print_output(output_queue, node_id.value + ' ')

        self.stop(1)

    def _success(self):
        print("Test run completed in {} seconds after {} steps.".format(
            self.time_elapsed, self.current_step + 1, ))
        self.stop(0)

    def next(self):
        if self.current_step == len(self.steps) - 1:
            self._success()
            return
        self.current_step += 1
        self.retry_counter = 0

    def previous(self):
        assert (self.current_step > 0), "Cannot move back past step 0"
        self.current_step -= 1
        self.retry_counter = 0

    def _wait_gnt_eth(self, node_id: NodeId, result):
        gnt_balance = helpers.to_ether(result.get('gnt'))
        gntb_balance = helpers.to_ether(result.get('av_gnt'))
        eth_balance = helpers.to_ether(result.get('eth'))
        if gnt_balance > 0 and eth_balance > 0 and gntb_balance > 0:
            print("{} has {} total GNT ({} GNTB) and {} ETH.".format(
                node_id.value, gnt_balance, gntb_balance, eth_balance))
            # FIXME: Remove this sleep when golem handles it ( #4221 )
            if self.has_requested_eth:
                time.sleep(30)
            self.next()

        else:
            print("Waiting for {} GNT(B)/converted GNTB/ETH ({}/{}/{})".format(
                node_id.value, gnt_balance, gntb_balance, eth_balance))
            self.has_requested_eth = True
            time.sleep(15)

    def step_wait_for_gnt(self, node_id: NodeId):
        def on_success(result):
            return self._wait_gnt_eth(node_id, result)
        return self.call(node_id, 'pay.balance', on_success=on_success)

    def step_get_key(self, node_id: NodeId):
        def on_success(result):
            print(f"{node_id.value} key: {result}")
            self.nodes_keys[node_id] = result
            self.next()

        def on_error(_):
            print(f"Waiting for the {node_id.value} node...")
            time.sleep(3)

        return self.call(node_id, 'net.ident.key',
                         on_success=on_success, on_error=on_error)

    def step_configure(self, node_id: NodeId):
        opts = self.config.current_nodes[node_id].opts
        if not opts:
            self.next()
            return

        def on_success(_):
            print(f"Configured {node_id.value}")
            self.next()

        def on_error(_):
            print(f"failed configuring {node_id.value}")
            self.fail()

        return self.call(node_id, 'env.opts.update', opts,
                         on_success=on_success, on_error=on_error)

    def step_get_network_info(self, node_id: NodeId):
        def on_success(result):
            if result.get('listening') and result.get('port_statuses'):
                ports = list(result.get('port_statuses').keys())
                port = ports[0]
                self.nodes_ports[node_id] = port
                print(f"{node_id.value}'s port: {port} (all: {ports})")
                self.next()
            else:
                print(f"Waiting for {node_id.value}'s network info...")
                time.sleep(3)

        return self.call(node_id, 'net.status', on_success=on_success)

    def step_connect(self, node_id: NodeId, target_node: NodeId):
        def on_success(result):
            print("Peer connection initialized.")
            self.reconnect_countdown = self.RECONNECT_COUNTDOWN_INITIAL
            self.next()
        return self.call(node_id, 'net.peer.connect',
                         ("localhost", self.nodes_ports[target_node]),
                         on_success=on_success)

    def step_verify_connection(self, node_id: NodeId, target_node: NodeId):
        def on_success(result):
            result_peer_keys: typing.Set[str] = \
                {peer['key_id'] for peer in result}

            expected_peer_keys: typing.Set[str] = set(self.nodes_keys.values())
            unexpected_peer_keys: typing.Set[str] = \
                result_peer_keys - expected_peer_keys

            if unexpected_peer_keys:
                print(f"{node_id.value} connected with unexpected peers:"
                      f" {unexpected_peer_keys}")
                self.fail()
                return

            if self.nodes_keys[target_node] not in result_peer_keys:
                if self.reconnect_countdown > 0:
                    self.reconnect_countdown -= 1
                    print("Waiting for nodes to sync...")
                    time.sleep(10)
                    return

                if self.reconnect_attempts_left > 0:
                    self.reconnect_attempts_left -= 1
                    print("Retrying peer connection.")
                    self.previous()
                    return

                self.fail("Could not sync nodes despite trying hard.")
                return

            print(f"{node_id.value} connected with {target_node.value}.")
            self.next()

        return self.call(node_id, 'net.peers.connected', on_success=on_success)

    def step_get_known_tasks(self, node_id: NodeId = NodeId.requestor):
        def on_success(result):
            self.known_tasks = set(map(lambda r: r['id'], result))
            print(f"Got current tasks list from the {node_id.value}.")
            self.next()

        return self.call(node_id, 'comp.tasks', on_success=on_success)

    def step_create_task(self, node_id: NodeId = NodeId.requestor):
        print("Output path: {}".format(self.output_path))
        print("Task dict: {}".format(self.config.task_dict))

        def on_success(result):
            if result[0]:
                print("Created task.")
                self.task_in_creation = False
                self.next()
            else:
                msg = result[1]
                if re.match('Not enough GNT', msg):
                    print(f"Waiting for {node_id.value}'s GNTB...")
                    time.sleep(30)
                    self.task_in_creation = False
                else:
                    print("Failed to create task {}".format(msg))
                    self.fail()

        if not self.task_in_creation:
            self.task_in_creation = True
            return self.call(node_id, 'comp.task.create', self.config.task_dict,
                             on_success=on_success)

    def step_get_task_id(self, node_id: NodeId = NodeId.requestor):

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

        return self.call(node_id, 'comp.tasks', on_success=on_success)

    def step_get_task_status(self, node_id: NodeId = NodeId.requestor):
        def on_success(result):
            print("Task status: {}".format(result['status']))
            self.next()

        return self.call(node_id, 'comp.task', self.task_id,
                         on_success=on_success)

    def step_wait_task_finished(self, node_id: NodeId = NodeId.requestor):
        def on_success(result):
            if result['status'] == 'Finished':
                print("Task finished.")
                self.next()
            elif result['status'] == 'Timeout':
                self.fail("Task timed out :( ... ")
            else:
                print("{} ... ".format(result['status']))
                time.sleep(10)

        return self.call(node_id, 'comp.task', self.task_id,
                         on_success=on_success)

    def step_verify_output(self):
        settings = self.task_settings_dict
        output_file_name = settings.get('name') + '.' + self.output_extension

        print("Verifying output file: {}".format(output_file_name))
        found_files = list(
            Path(self.output_path).glob(f'**/{output_file_name}')
        )

        if len(found_files) > 0 and found_files[0].is_file():
            print("Output present :)")
            self.next()
        else:
            print("Failed to find the output.")
            self.fail()

    def step_get_subtasks(self, node_id: NodeId = NodeId.requestor,
                          statuses: typing.Set[str] = {'Finished'}):
        def on_success(result):
            subtasks = {
                self.nodes_keys.inverse[s['node_id']]: s.get('subtask_id')
                for s in result
                if s.get('status') in statuses
            }
            for k, v in subtasks.items():
                if k not in self.subtasks:
                    self.subtasks[k] = {v}
                else:
                    self.subtasks[k].add(v)

            if not self.subtasks:
                self.fail("No subtasks found???")
            self.next()

        return self.call(node_id, 'comp.task.subtasks', self.task_id,
                         on_success=on_success)

    def step_verify_income(self,
                           node_id: NodeId = NodeId.provider,
                           from_node: NodeId = NodeId.requestor):
        def on_success(result):
            payments = {
                p.get('subtask')
                for p in result
                if p.get('payer') == self.nodes_keys[from_node]
            }
            unpaid = self.subtasks[node_id] - payments
            if unpaid:
                print("Found subtasks with no matching payments: %s" % unpaid)
                time.sleep(3)
                return

            print("All subtasks accounted for.")
            self.next()

        return self.call(node_id, 'pay.incomes', on_success=on_success)

    def step_stop_nodes(self):
        if self.nodes_started:
            print("Stopping nodes")
            self.stop_nodes()

        time.sleep(10)
        self._poll_exit_codes()
        if any(exit_code is None
               for exit_code in self.nodes_exit_codes.values()):
            print("...")
            return

        if any(exit_code != 0 for exit_code in self.nodes_exit_codes.values()):
            for node_id, exit_code in self.nodes_exit_codes.items():
                if exit_code != 0:
                    print(f"Abnormal termination {node_id.value}: {exit_code}")
            self.fail()
            return

        print("Stopped nodes")
        self.next()

    def step_restart_nodes(self):
        print("Starting nodes again")
        self.config.use_next_nodes()

        self.task_in_creation = False
        time.sleep(60)

        self.start_nodes()
        print("Nodes restarted")
        self.next()

    initial_steps: typing.Tuple = (
        partial(step_get_key, node_id=NodeId.provider),
        partial(step_get_key, node_id=NodeId.requestor),
        partial(step_configure, node_id=NodeId.provider),
        partial(step_configure, node_id=NodeId.requestor),
        partial(step_get_network_info, node_id=NodeId.provider),
        partial(step_get_network_info, node_id=NodeId.requestor),
        partial(step_connect, node_id=NodeId.requestor,
                target_node=NodeId.provider),
        partial(step_verify_connection, node_id=NodeId.requestor,
                target_node=NodeId.provider),
        partial(step_wait_for_gnt, node_id=NodeId.requestor),
        step_get_known_tasks,
    )

    steps: typing.Tuple = initial_steps + (
        step_create_task,
        step_get_task_id,
        step_get_task_status,
        step_wait_task_finished,
        step_verify_output,
        step_get_subtasks,
        step_verify_income,
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

    def call(self, node_id: NodeId, method: str, *args,
             on_success=print_result,
             on_error=print_error,
             **kwargs):
        node_config = self.config.current_nodes[node_id]
        return self._call_rpc(
            method,
            port=node_config.rpc_port,
            datadir=node_config.datadir,
            *args,
            on_success=catch_and_print_exceptions(on_success),
            on_error=catch_and_print_exceptions(on_error),
            **kwargs,
        )

    def start_nodes(self):
        for node_id, node_config in self.config.current_nodes.items():
            print(f"{node_id.value} config: {repr(node_config)}")
            node = helpers.run_golem_node(
                node_config.script,
                node_config.make_args(),
                nodes_root=self.config.nodes_root,
            )
            self.nodes[node_id] = node
            self.output_queues[node_id] = helpers.get_output_queue(node)

        self.nodes_started = True

    def stop_nodes(self):
        if not self.nodes_started:
            return

        for node_id, node in self.nodes.items():
            helpers.gracefully_shutdown(node, node_id.value)

        self.nodes_started = False

    def _poll_exit_codes(self):
        self.nodes_exit_codes = {
            node_id: node.poll()
            for node_id, node
            in self.nodes.items()
        }

    def run(self):
        if self.nodes_started:
            self._poll_exit_codes()
            if any(exit_code is not None
                   for exit_code in self.nodes_exit_codes.values()):
                for node_id, exit_code in self.nodes_exit_codes.items():
                    helpers.report_termination(exit_code, node_id.value)
                self.fail("A node exited abnormally.")

        try:
            self.retry_counter += 1
            if self.retry_counter >= 100:
                raise Exception("Step tried 100 times, failing")
            method = self.current_step_method
            return method(self)
        except Exception as e:  # noqa pylint:disable=too-broad-exception
            e, msg, tb = sys.exc_info()
            print("Exception {}: {} on step {}: {}".format(
                e.__name__, msg, self.current_step, self.current_step_name))
            traceback.print_tb(tb)
            self.fail()
            return

    def start(self) -> None:
        self.start_time = time.time()
        d = self._loop.start(self.INTERVAL, False)
        d.addErrback(lambda x: print(x))

        reactor.addSystemEventTrigger(
            'before', 'shutdown', lambda: self.stop(2))
        reactor.run()

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
