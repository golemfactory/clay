#!/usr/bin/env python
import re
import sys
import tempfile
import time
import traceback

from twisted.internet import reactor, task
from twisted.internet.error import ReactorNotRunning
from twisted.internet import _sslverify  # pylint: disable=protected-access

from scripts.concent_node_tests.rpc.client import call_requestor, call_provider
from scripts.concent_node_tests import helpers

_sslverify.platformTrust = lambda: None

class NodeTestPlaybook:
    INTERVAL = 1

    _instance = None

    provider_node_script = None
    requestor_node_script = None
    provider_node = None
    requestor_node = None
    provider_port = None

    exit_code = None
    current_step = 0
    provider_key = None
    requestor_key = None
    known_tasks = None
    task_id = None

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

    def fail(self, msg=None):
        print(msg or "Test run failed on step {}: {}".format(
                self.current_step, self.current_step_name))
        self.stop(1)

    def success(self):
        print("Test run completed after {} steps.".format(
            self.current_step + 1))
        self.stop(0)

    def next(self):
        self.current_step += 1

    def print_result(self, result):
        print("Result: {}".format(result))

    def print_error(self, error):
        print("Error: {}".format(error))

    def step_get_provider_key(self):
        def on_success(result):
            print("Provider key", result)
            self.provider_key = result
            self.next()

        def on_error(result):
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
            match = re.search(r'Port\s(\d+)', result)
            if match:
                self.provider_port = match.group(1)
                print("Provider's port: {}".format(self.provider_port))
                self.next()
            else:
                print("Waiting for Provider's network info...")
                time.sleep(3)
        call_provider('net.status',
                      on_success=on_success, on_error=lambda: None)

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
        task_dict = helpers.construct_test_task(
            'test_task_1', tempfile.mkdtemp())

        def on_success(result):
            if result[0]:
                print("Created task.")
                self.next()
            else:
                print("Failed to create task {}".format(result))
                self.fail()

        call_requestor('comp.task.create', task_dict,
                       on_success=on_success,
                       on_error=self.print_error)

    def step_get_task_id(self):

        def on_success(result):
            tasks = set(map(lambda r: r['id'], result))
            new_tasks = tasks - self.known_tasks
            if len(new_tasks) != 1:
                print("Cannot find the new task ({})".format(new_tasks))

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
                self.success()
            else:
                print("{} ... ".format(result['status']))
                time.sleep(5)

        call_requestor('comp.task', self.task_id,
                       on_success=on_success, on_error=self.print_error)

    steps = (
        step_get_provider_key,
        step_get_requestor_key,
        step_get_provider_network_info,
        step_connect_nodes,
        step_verify_peer_connection,
        step_get_known_tasks,
        step_create_task,
        step_get_task_id,
        step_get_task_status,
        step_wait_task_finished,
    )

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

        provider_exit = self.provider_node.poll()
        requestor_exit = self.requestor_node.poll()
        helpers.report_termination(provider_exit, "Provider")
        helpers.report_termination(requestor_exit, "Requestor")
        if provider_exit is not None and requestor_exit is not None:
            self.fail()

    def __init__(self):
        if not self.provider_node_script or not self.requestor_node_script:
            raise NotImplementedError(
                "Provider and Requestor scripts need to be set")

        self.provider_node = helpers.run_golem_node(
            self.provider_node_script
        )
        self.requestor_node = helpers.run_golem_node(
            self.requestor_node_script
        )

    @classmethod
    def start(cls):
        playbook = cls()
        p =  task.LoopingCall(playbook.run)
        p.start(cls.INTERVAL, False)
        playbook._instance = p

        reactor.addSystemEventTrigger(
            'before', 'shutdown', lambda: playbook.stop(2))
        reactor.run()

        return playbook

    def stop(self, exit_code):
        try:
            reactor.stop()
        except ReactorNotRunning:
            pass

        helpers.gracefully_shutdown(self.provider_node, 'Provider')
        helpers.gracefully_shutdown(self.requestor_node, 'Requestor')

        self.exit_code = exit_code
