# Test script for running a single instance of a dummy task.
# The task simply computes hashes of some random data and requires
# no external tools. The amount of data processed (ie hashed) and computational
# difficulty is configurable, see comments in DummyTaskParameters.

from task import DummyTask, DummyTaskParameters
from golem.client import start_client
from golem.environments.environment import Environment
from golem.network.transport.tcpnetwork import TCPAddress

import os
import re
import select
import subprocess
import sys
import time
from twisted.internet import reactor


REQUESTING_NODE_ARG = "requester"
COMPUTING_NODE_ARG = "computer"


def run_requesting_node(num_subtasks = 3):

    def report(msg):
        print "[REQUESTING NODE {}] {}".format(os.getpid(), msg)

    start_time = time.time()
    report("Starting...")
    client = start_client()
    report("Started in {:.1f} s".format(time.time() - start_time))

    params = DummyTaskParameters(1024, 2048, 256, 0x0001ffff)
    task = DummyTask(client.get_node_name(), params, num_subtasks)
    client.enqueue_new_task(task)

    port = client.p2pservice.cur_port
    requester_addr = "{}:{}".format(client.node.prv_addr, port)
    report("Listening on: {}".format(requester_addr))

    def report_status():
        finished = False
        while True:
            time.sleep(5)
            report("Ping!")
            if not finished and task.finished_computation():
                report("Task finished")
                finished = True

    reactor.callInThread(report_status)
    reactor.run()


def run_computing_node(peer_address):

    def report(msg):
        print "[COMPUTING NODE {}] {}".format(os.getpid(), msg)

    start_time = time.time()
    report("Starting...")
    client = start_client()
    report("Started in {:.1f} s".format(time.time() - start_time))

    class DummyEnvironment(Environment):
        @classmethod
        def get_id(cls):
            return "DUMMY"

    dummy_env = DummyEnvironment()
    dummy_env.accept_tasks = True
    client.environments_manager.add_environment(dummy_env)

    report("Connecting to requester node at {}:{} ..."
           .format(peer_address.address, peer_address.port))
    client.connect(peer_address)

    def report_status():
        while True:
            time.sleep(5)
            report("Ping!")

    reactor.callInThread(report_status)
    reactor.run()


def run_simulation(num_computing_nodes = 2, num_subtasks = 3, timeout = 120):
    # We need to pass the PYTHONPATH to the child processes
    pythonpath = "".join(dir + ":" for dir in sys.path)
    env = os.environ
    env["PYTHONPATH"] = pythonpath

    start_time = time.time()

    # Start the requesting node in a separate process
    requesting_proc = subprocess.Popen(
        ["python", "-u", __file__, REQUESTING_NODE_ARG, str(num_subtasks)],
        bufsize = 1,  # line buffered
        env = env,
        stdout = subprocess.PIPE)

    # Scan the requesting node's stdout for the address
    address_re = re.compile("\[REQUESTING NODE [0-9]+\] Listening on: (.+)")
    while True:
        line = requesting_proc.stdout.readline().strip()
        print line
        m = address_re.match(line)
        if m:
            requester_address = m.group(1)
            break

    # Start computing nodes in a separate processes
    computing_procs = []
    for n in range(0, num_computing_nodes):
        proc = subprocess.Popen(
            ["python", "-u", __file__, COMPUTING_NODE_ARG, requester_address],
            bufsize = 1,
            env = env,
            stdout = subprocess.PIPE)

        computing_procs.append(proc)

    all_procs = computing_procs + [requesting_proc]
    task_finished_status = "[REQUESTING NODE {}] Task finished".format(
        requesting_proc.pid)

    def monitor(processes):
        descriptors = [proc.stdout for proc in processes]

        while True:
            if time.time() - start_time > timeout:
                return "Computation timed out"

            # Check if all subprocesses are alive
            for proc in processes:
                if proc.returncode:
                    return "Node exited with return code {}".\
                        format(proc.returncode)

            # Monitor subprocesses' output
            ready = select.select(descriptors, [], [], 5.0)[0]
            for f in ready:
                line = f.readline().strip()
                print line
                if line == task_finished_status:
                    return None

            if not ready:
                time.sleep(1.0)

    # Wait until timeout elapses or the task is computed
    try:
        error_msg = monitor(all_procs)
        return error_msg
    finally:
        for proc in all_procs:
            if not proc.returncode:
                proc.kill()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == REQUESTING_NODE_ARG:
        # I'm a requesting node, second arg is the number of subtasks
        run_requesting_node(int(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == COMPUTING_NODE_ARG:
        # I'm a computing node, second arg is the address to connect to
        run_computing_node(TCPAddress.parse(sys.argv[2]))
    elif len(sys.argv) == 1:
        # I'm the main script, run simulation
        error_msg = run_simulation(
            num_computing_nodes = 2, num_subtasks = 4, timeout = 120)
        if error_msg:
            print "Dummy task computation failed:", error_msg
            sys.exit(1)
