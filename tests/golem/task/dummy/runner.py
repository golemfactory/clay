"""Test script for running a single instance of a dummy task.
The task simply computes hashes of some random data and requires
no external tools. The amount of data processed (ie hashed) and computational
difficulty is configurable, see comments in DummyTaskParameters.
"""
import atexit
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from os import path
from threading import Thread

from twisted.internet import reactor

from golem.environments.environment import Environment
from golem.resource.dirmanager import DirManager
from golem.network.transport.tcpnetwork import SocketAddress
from task import DummyTask, DummyTaskParameters

REQUESTING_NODE_KIND = "requestor"
COMPUTING_NODE_KIND = "computer"


def format_msg(kind, pid, msg):
    return "[{} {:>5}] {}".format(kind, pid, msg)


node_kind = ""


def report(msg):
    print format_msg(node_kind, os.getpid(), msg)


def override_ip_info(*_, **__):
    from stun import OpenInternet
    return OpenInternet, '1.2.3.4', 40102


def create_client(datadir):
    # executed in a subprocess
    import stun
    stun.get_ip_info = override_ip_info

    from golem.client import Client
    return Client(datadir=datadir,
                  use_monitor=False,
                  transaction_system=False,
                  connect_to_known_hosts=False,
                  use_docker_machine_manager=False,
                  estimated_lux_performance=1000.0,
                  estimated_blender_performance=1000.0)


def run_requesting_node(datadir, num_subtasks=3):
    client = None

    def shutdown():
        client and client.quit()
        logging.shutdown()
    atexit.register(shutdown)

    global node_kind
    node_kind = "REQUESTOR"

    start_time = time.time()
    report("Starting in {}".format(datadir))
    client = create_client(datadir)
    client.start()
    report("Started in {:.1f} s".format(time.time() - start_time))

    params = DummyTaskParameters(1024, 2048, 256, 0x0001ffff)
    task = DummyTask(client.get_node_name(), params, num_subtasks)
    task.initialize(DirManager(datadir))
    client.enqueue_new_task(task)

    port = client.p2pservice.cur_port
    requestor_addr = "{}:{}".format(client.node.prv_addr, port)
    report("Listening on {}".format(requestor_addr))

    def report_status():
        while True:
            time.sleep(1)
            if task.finished_computation():
                report("Task finished")
                shutdown()
                return

    reactor.callInThread(report_status)
    reactor.run()
    return client  # Used in tests, with mocked reactor


def run_computing_node(datadir, peer_address, fail_after=None):
    client = None

    def shutdown():
        client and client.quit()
        logging.shutdown()
    atexit.register(shutdown)

    global node_kind
    node_kind = "COMPUTER "

    start_time = time.time()
    report("Starting in {}".format(datadir))
    client = create_client(datadir)
    client.start()
    client.task_server.task_computer.support_direct_computation = True
    report("Started in {:.1f} s".format(time.time() - start_time))

    class DummyEnvironment(Environment):
        @classmethod
        def get_id(cls):
            return DummyTask.ENVIRONMENT_NAME

        def __init__(self):
            super(DummyEnvironment, self).__init__()
            self.allow_custom_main_program_file = True

    dummy_env = DummyEnvironment()
    dummy_env.accept_tasks = True
    client.environments_manager.add_environment(dummy_env)

    report("Connecting to requesting node at {}:{} ..."
           .format(peer_address.address, peer_address.port))
    client.connect(peer_address)

    def report_status(fail_after=None):
        t0 = time.time()
        while True:
            if fail_after and time.time() - t0 > fail_after:
                report("Failure!")
                reactor.callFromThread(reactor.stop)
                shutdown()
                return
            time.sleep(1)

    reactor.callInThread(report_status, fail_after)
    reactor.run()
    return client  # Used in tests, with mocked reactor


# Global var set by a thread monitoring the status of the requestor node
task_finished = False


def run_simulation(num_computing_nodes=2, num_subtasks=3, timeout=120,
                   node_failure_times=None):

    # We need to pass the PYTHONPATH to the child processes
    pythonpath = "".join(dir + os.pathsep for dir in sys.path)
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath

    datadir = tempfile.mkdtemp(prefix='golem_dummy_simulation_')

    start_time = time.time()

    # Start the requesting node in a separate process
    reqdir = path.join(datadir, REQUESTING_NODE_KIND)
    requesting_proc = subprocess.Popen(
        ["python", "-u", __file__, REQUESTING_NODE_KIND, reqdir, str(num_subtasks)],
        bufsize=1,  # line buffered
        env=env,
        stdout=subprocess.PIPE)

    # Scan the requesting node's stdout for the address
    address_re = re.compile(".+REQUESTOR.+Listening on (.+)")
    while True:
        line = requesting_proc.stdout.readline().strip()
        if line:
            print line
            m = address_re.match(line)
            if m:
                requestor_address = m.group(1)
                break

    # Start computing nodes in a separate processes
    computing_procs = []
    for n in range(0, num_computing_nodes):
        compdir = path.join(datadir, COMPUTING_NODE_KIND + str(n))
        cmdline = [
            "python", "-u", __file__, COMPUTING_NODE_KIND, compdir, requestor_address]
        if node_failure_times and len(node_failure_times) > n:
            # Simulate failure of a computing node
            cmdline.append(str(node_failure_times[n]))
        proc = subprocess.Popen(
            cmdline,
            bufsize=1,
            env=env,
            stdout=subprocess.PIPE)
        computing_procs.append(proc)

    all_procs = computing_procs + [requesting_proc]
    task_finished_status = format_msg(
        "REQUESTOR", requesting_proc.pid, "Task finished")

    global task_finished
    task_finished = False

    def monitor_subprocess(proc):
        global task_finished
        while proc.returncode is None:
            line = proc.stdout.readline().strip()
            if line:
                print line
            if line == task_finished_status:
                task_finished = True

    monitor_threads = [Thread(target=monitor_subprocess,
                              name="monitor {}".format(p.pid),
                              args=(p,))
                       for p in all_procs]

    for th in monitor_threads:
        th.setDaemon(True)
        th.start()

    # Wait until timeout elapses or the task is computed
    try:
        while not task_finished:
            if time.time() - start_time > timeout:
                return "Computation timed out"
            # Check if all subprocesses are alive
            for proc in all_procs:
                if proc.poll() is not None:
                    return "Node exited with return code {}".format(
                        proc.returncode)
            time.sleep(1)
        return None
    finally:
        print "Stopping nodes..."

        for proc in all_procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
                del proc

        time.sleep(1)
        shutil.rmtree(datadir)


def dispatch(args):
    if len(args) == 4 and args[1] == REQUESTING_NODE_KIND:
        # I'm a requesting node,
        # second arg is the data dir,
        # third arg is the number of subtasks.
        run_requesting_node(args[2], int(args[3]))
    elif len(args) in [4, 5] and args[1] == COMPUTING_NODE_KIND:
        # I'm a computing node,
        # second arg is the data dir,
        # third arg is the address to connect to,
        # forth arg is the timeout (optional).
        fail_after = float(args[4]) if len(args) == 5 else None
        run_computing_node(args[2], SocketAddress.parse(args[3]), fail_after=fail_after)
    elif len(args) == 1:
        # I'm the main script, run simulation
        error_msg = run_simulation(num_computing_nodes=2, num_subtasks=4,
                                   timeout=120)
        if error_msg:
            print "Dummy task computation failed:", error_msg
            sys.exit(1)


if __name__ == "__main__":
    dispatch(sys.argv)
