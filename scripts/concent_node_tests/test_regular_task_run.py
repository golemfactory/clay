#!/usr/bin/env python
import sys
import tempfile
import time

from twisted.internet import reactor, task
from twisted.internet import _sslverify  # pylint: disable=protected-access

from scripts.concent_node_tests.rpc.client import call_requestor, call_provider
from scripts.concent_node_tests.helpers import construct_test_task

_sslverify.platformTrust = lambda: None


class RunTask:
    step = 1
    provider_key = None
    known_tasks = None
    task_id = None

    def fail(self):
        reactor.stop()
        sys.exit(1)

    def success(self):
        print("Test run completed! :)")
        reactor.stop()
        sys.exit(0)

    def next(self):
        self.step += 1

    def print_result(self, result):
        print("Result: {}".format(result))

    def print_error(self, error):
        print("Error: {}".format(error))

    def step_1(self):
        def on_success(result):
            print("Provider key", result)
            self.provider_key = result
            self.next()

        call_provider('net.ident.key', on_success=on_success, on_error=self.print_error)

    def step_2(self):
        def on_success(result):
            if len(result) > 1:
                print("Too many peers")
                self.fail()
            elif len(result) == 1:
                peer = result[0]
                if peer['key_id'] != self.provider_key:
                    print("Connected peer: {} != provider peer: {}",
                          peer.key, self.provider_key)
                    self.fail()

                print("Requestor connected with provider.")
                self.next()

        call_requestor('net.peers.connected', on_success=on_success, on_error=self.print_error)

    def step_3(self):
        def on_success(result):
            self.known_tasks = set(map(lambda r: r['id'], result))
            print("Got current tasks list from the requestor.")
            self.next()

        call_requestor('comp.tasks', on_success=on_success, on_error=self.print_error)

    def step_4(self):
        task_dict = construct_test_task('test_task_1', tempfile.mkdtemp())

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

    def step_5(self):

        def on_success(result):
            tasks = set(map(lambda r: r['id'], result))
            new_tasks = tasks - self.known_tasks
            if len(new_tasks) != 1:
                print("Cannot find the new task ({})".format(new_tasks))

            self.task_id = list(new_tasks)[0]
            print("Task id: {}".format(self.task_id))
            self.next()

        call_requestor('comp.tasks', on_success=on_success, on_error=self.print_error)

    def step_6(self):
        def on_success(result):
            print("Task status: {}".format(result['status']))
            self.next()

        call_requestor('comp.task', self.task_id, on_success=on_success, on_error=self.print_error)

    def step_7(self):
        def on_success(result):
            if result['status'] == 'Finished':
                print("Task finished.")
                self.success()
            else:
                print("{} ... ".format(result['status']))
                time.sleep(5)

        call_requestor('comp.task', self.task_id, on_success=on_success, on_error=self.print_error)

    def run(self):
        method = getattr(self, 'step_' + str(self.step), None)
        if callable(method):
            method()
        else:
            print("Ran out of steps on step {}".format(self.step))
            self.fail()


playbook = RunTask()
p = task.LoopingCall(playbook.run)
p.start(1, False)

try:
    reactor.run()
except KeyboardInterrupt:
    reactor.stop()
