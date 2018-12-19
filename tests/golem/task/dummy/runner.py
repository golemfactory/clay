"""Test script for running a single instance of a dummy task.
The task simply computes hashes of some random data and requires
no external tools. The amount of data processed (ie hashed) and computational
difficulty is configurable, see comments in DummyTaskParameters.
"""
import atexit
import logging
import os
from os import path
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from unittest import mock
from threading import Thread
import faker

from ethereum.utils import denoms
from twisted.internet import reactor

from golem.appconfig import AppConfig
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.variables import CONCENT_CHOICES
from golem.database import Database
from golem.environments.environment import Environment
from golem.resource.dirmanager import DirManager
from golem.task import rpc as task_rpc
from golem.model import db, DB_FIELDS, DB_MODELS
from golem.network.transport.tcpnetwork import SocketAddress
from tests.golem.task.dummy.task import DummyTask, DummyTaskParameters

REQUESTING_NODE_KIND = "requestor"
COMPUTING_NODE_KIND = "computer"

logger = logging.getLogger(__name__)


class DummyEnvironment(Environment):
    @classmethod
    def get_id(cls):
        return DummyTask.ENVIRONMENT_NAME

    def __init__(self):
        super(DummyEnvironment, self).__init__()
        self.allow_custom_main_program_file = True


def format_msg(kind, pid, msg):
    return "[{} {:>5}] {}".format(kind, pid, msg)


node_kind = ""


def report(msg):
    print(format_msg(node_kind, os.getpid(), msg))


def override_ip_info(*_, **__):
    return '1.2.3.4', 40102


def create_client(datadir):
    # executed in a subprocess
    from golem.network.stun import pystun
    pystun.get_ip_info = override_ip_info

    from golem.client import Client
    app_config = AppConfig.load_config(datadir)
    config_desc = ClientConfigDescriptor()
    config_desc.init_from_app_config(app_config)
    config_desc.key_difficulty = 0
    config_desc.use_upnp = False

    from golem.core.keysauth import KeysAuth
    with mock.patch.dict('ethereum.keys.PBKDF2_CONSTANTS', {'c': 1}):
        keys_auth = KeysAuth(
            datadir=datadir,
            private_key_name=faker.Faker().pystr(),
            password='password',
            difficulty=config_desc.key_difficulty,
        )

    database = Database(
        db, fields=DB_FIELDS, models=DB_MODELS, db_dir=datadir)

    from golem.hardware.presets import HardwarePresets
    HardwarePresets.initialize(datadir)
    HardwarePresets.update_config('default', config_desc)

    ets = _make_mock_ets()
    return Client(datadir=datadir,
                  app_config=app_config,
                  config_desc=config_desc,
                  keys_auth=keys_auth,
                  database=database,
                  transaction_system=ets,
                  use_monitor=False,
                  connect_to_known_hosts=False,
                  use_docker_manager=False,
                  concent_variant=CONCENT_CHOICES['disabled'])


def _make_mock_ets():
    available_gntb = 1000 * denoms.ether
    ets = mock.Mock()
    ets.get_balance.return_value = (
        available_gntb,  # GNTB
        1000 * denoms.ether,  # locked
        1000 * denoms.ether,  # GNT
        time.time(),
        time.time(),
    )
    ets.get_available_gnt.return_value = available_gntb
    ets.eth_for_batch_payment.return_value = 0.0001 * denoms.ether
    ets.eth_base_for_batch_payment.return_value = 0.001 * denoms.ether
    ets.get_payment_address.return_value = '0x' + 40 * '6'
    ets.get_nodes_with_overdue_payments.return_value = []
    return ets


def _print_golem_log(datadir):
    """ Prints the log file at the end of the test
        TODO: Check why it is not always triggered
    """
    logfile = path.join(datadir, "logs", "golem.log")
    with open(logfile, 'r') as file:
        data = file.read()
        report("golem.log: >>>\n{}\n<<<end golem.log".format(data))


def run_requesting_node(datadir, num_subtasks=3):
    client = None

    def shutdown():
        client and client.quit()
        reactor.running and reactor.callFromThread(reactor.stop)
        logging.shutdown()
        if os.path.exists(datadir):
            _print_golem_log(datadir)
            shutil.rmtree(datadir)

    atexit.register(shutdown)

    global node_kind
    node_kind = "REQUESTOR"

    start_time = time.time()
    report("Starting in {}".format(datadir))
    from golem.core.common import config_logging
    config_logging(datadir=datadir, loglevel="DEBUG")

    client = create_client(datadir)
    client.are_terms_accepted = lambda: True
    client.start()
    report("Started in {:.1f} s".format(time.time() - start_time))

    dummy_env = DummyEnvironment()
    client.environments_manager.add_environment(dummy_env)

    params = DummyTaskParameters(1024, 2048, 256, 0x0001ffff)
    task = DummyTask(client.get_node_name(), params, num_subtasks,
                     client.keys_auth.public_key)
    task.initialize(DirManager(datadir))
    task_rpc.enqueue_new_task(client, task)

    port = client.p2pservice.cur_port
    requestor_addr = "{}:{}".format(client.node.prv_addr, port)
    report("Listening on {}".format(requestor_addr))

    def report_status():
        while True:
            time.sleep(1)
            if not task.finished_computation():
                continue
            if task.verify_task():
                report("Task finished")
            else:
                report("Task failed")
            shutdown()
            return

    reactor.callInThread(report_status)
    reactor.run()
    return client  # Used in tests, with mocked reactor


def run_computing_node(datadir, peer_address, fail_after=None):
    client = None

    def shutdown():
        client and client.quit()
        reactor.running and reactor.callFromThread(reactor.stop)
        logging.shutdown()
        if os.path.exists(datadir):
            _print_golem_log(datadir)
            shutil.rmtree(datadir)

    atexit.register(shutdown)

    global node_kind
    node_kind = "COMPUTER "

    start_time = time.time()
    report("Starting in {}".format(datadir))
    from golem.core.common import config_logging
    config_logging(datadir=datadir, loglevel="DEBUG")

    client = create_client(datadir)
    client.are_terms_accepted = lambda: True
    client.start()
    client.task_server.task_computer.support_direct_computation = True
    report("Started in {:.1f} s".format(time.time() - start_time))

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
task_result = None


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
    reqdir_path = pathlib.Path(reqdir)
    (reqdir_path / 'logs').mkdir(parents=True)
    requesting_proc = subprocess.Popen(
        [sys.executable, "-u", __file__, REQUESTING_NODE_KIND, reqdir,
         str(num_subtasks)],
        bufsize=1,  # line buffered
        env=env,
        stdout=subprocess.PIPE)

    # Scan the requesting node's stdout for the address
    address_re = re.compile(".+REQUESTOR.+Listening on (.+)")
    while requesting_proc.poll() is None:
        line = requesting_proc.stdout.readline().strip()
        if line:
            line = line.decode('utf-8')
            print(line)
            m = address_re.match(line)
            if m:
                requestor_address = m.group(1)
                break

    if requesting_proc.poll() is not None:
        logger.error("Requestor proc not started")
        shutil.rmtree(datadir)
        return "ERROR"

    # Start computing nodes in a separate processes
    computing_procs = []
    for n in range(0, num_computing_nodes):
        compdir = path.join(datadir, COMPUTING_NODE_KIND + str(n))
        cmdline = [
            sys.executable, "-u", __file__, COMPUTING_NODE_KIND,
            compdir, requestor_address
        ]
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
    task_failed_status = format_msg(
        "REQUESTOR", requesting_proc.pid, "Task failed")

    global task_result
    task_result = None

    def monitor_subprocess(proc):
        global task_result

        while proc.returncode is None:
            line = proc.stdout.readline().strip()
            if line:
                line = line.decode('utf-8')
                print(line)
            if line == task_finished_status:
                task_result = True
            elif line == task_failed_status:
                task_result = False

    monitor_threads = [Thread(target=monitor_subprocess,
                              name="monitor {}".format(p.pid),
                              args=(p,))
                       for p in all_procs]

    for th in monitor_threads:
        th.setDaemon(True)
        th.start()

    # Wait until timeout elapses or the task is computed
    try:
        while task_result is None:
            if time.time() - start_time > timeout:
                return "Computation timed out"
            # Check if all subprocesses are alive
            for proc in all_procs:
                if proc.poll() is not None:
                    return "Node exited with return code {}".format(
                        proc.returncode)
            time.sleep(1)

        if not task_result:
            return "Task computation failed"
        return None
    finally:
        print("Stopping nodes...")

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
        run_computing_node(args[2], SocketAddress.parse(args[3]),
                           fail_after=fail_after)
    elif len(args) == 1:
        # I'm the main script, run simulation
        error_msg = run_simulation(num_computing_nodes=2, num_subtasks=4,
                                   timeout=120)
        if error_msg:
            print("Dummy task computation failed:", error_msg)
            sys.exit(1)


if __name__ == "__main__":
    dispatch(sys.argv)
