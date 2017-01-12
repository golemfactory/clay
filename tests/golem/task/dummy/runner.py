"""
The task simply computes hashes of some random data and requires
no external tools. The amount of data processed (ie hashed) and computational
difficulty is configurable, see comments in DummyTaskParameters.
"""
import logging
import multiprocessing
import os
import shutil
import sys
import tempfile
import time
from Queue import Empty
from multiprocessing import Queue
from os import path

from twisted.internet.defer import setDebugging

from golem.environments.environment import Environment
from golem.network.transport.tcpnetwork import SocketAddress
from task import DummyTask, DummyTaskParameters

REQUESTING_NODE_KIND = "requestor"
COMPUTING_NODE_KIND = "computer"

MSG_STOP = "stop"
MSG_DONE = "done"


class DummyEnvironment(Environment):
    @classmethod
    def get_id(cls):
        return DummyTask.ENVIRONMENT_NAME


def report(kind, msg):
    print "[{} {:>5}] {}".format(kind, os.getpid(), msg)


def override_ip_info(*_, **__):
    from stun import OpenInternet
    return OpenInternet, '1.2.3.4', 40102


def setup_logging():

    setDebugging(True)
    formatter = logging.Formatter('%(asctime)s %(levelname)7s %(module)s - %(message)s')

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)


def queue_get(q):
    try:
        return q.get(block=False)
    except Empty:
        return None


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


def run_requesting_node(queue_in, queue_out, datadir, num_subtasks=3):
    from golem.resource.dirmanager import DirManager

    kind = REQUESTING_NODE_KIND
    start_time = time.time()

    report(kind, "Starting in {}".format(datadir))

    try:
        client = create_client(datadir)
        client.start()
    except Exception as exc:
        queue_out.put(exc)
        return

    report(kind, "Started in {:.1f} s".format(time.time() - start_time))

    params = DummyTaskParameters(1024, 2048, 256, 0x0001ffff)
    task = DummyTask(client.get_node_name(), params, num_subtasks)

    try:
        dir_manager = DirManager(datadir)
        task.initialize(dir_manager)
        client.enqueue_new_task(task)
    except Exception as exc:
        queue_out.put(exc)
        return

    address = SocketAddress(client.node.prv_addr, client.p2pservice.cur_port)
    queue_out.put(address)

    report(kind, "Listening on {}:{}".format(address.address, address.port))

    from twisted.internet import reactor
    from twisted.internet import task as twisted_task

    def check_status():
        if task.finished_computation():
            queue_out.put(MSG_DONE)

        msg = queue_get(queue_in)
        if msg == MSG_STOP:
            reactor.callFromThread(reactor.stop)

    def shutdown():
        client.quit()
        logging.shutdown()

    status_task = twisted_task.LoopingCall(check_status)
    status_task.start(1.)

    reactor.addSystemEventTrigger("before", "shutdown", shutdown)
    reactor.run()


def run_computing_node(queue_in, queue_out, datadir, peer_address, fail_after=None):
    dummy_env = DummyEnvironment()
    dummy_env.accept_tasks = True
    kind = COMPUTING_NODE_KIND

    start_time = time.time()
    report(kind, "Starting in {}".format(datadir))

    try:

        client = create_client(datadir)
        client.start()
        client.task_server.task_computer.support_direct_computation = True
        client.environments_manager.add_environment(dummy_env)

    except Exception as exc:
        queue_out.put(exc)
        raise

    report(kind, "Started in {:.1f} s".format(time.time() - start_time))
    report(kind, "Connecting to requesting node at {}:{} ..."
           .format(peer_address.address, peer_address.port))

    try:
        client.connect(peer_address)
    except Exception as exc:
        queue_out.put(exc)
        raise

    from twisted.internet import reactor
    from twisted.internet import task as twisted_task

    def check_status():
        msg = queue_get(queue_in)
        if msg == MSG_STOP:
            reactor.callFromThread(reactor.stop)

    def fail():
        queue_out.put(Exception("Timeout"))

    def shutdown():
        client.quit()
        logging.shutdown()

    status_task = twisted_task.LoopingCall(check_status)
    status_task.start(0.5)

    if fail_after:
        reactor.callLater(fail_after, fail)

    reactor.addSystemEventTrigger("before", "shutdown", shutdown)
    reactor.run()


def run_simulation(num_computing_nodes=2, num_subtasks=3, timeout=120,
                   node_failure_times=None):

    setup_logging()

    data_dir = tempfile.mkdtemp(prefix='golem_dummy_simulation_')
    processes = []

    # --- REQUESTOR ---

    req_dir = path.join(data_dir, REQUESTING_NODE_KIND)
    req_queue_in, req_queue_out = Queue(), Queue()

    req_proc = multiprocessing.Process(
        target=run_requesting_node,
        args=(req_queue_out, req_queue_in, req_dir, num_subtasks)
    )
    req_proc.start()

    processes.append(req_proc)

    try:
        req_address = req_queue_in.get(block=True, timeout=60)
    except Empty:
        req_address = None

    if not isinstance(req_address, SocketAddress):
        req_queue_out.put(MSG_STOP)
        return "Invalid address: {}".format(req_address)

    # --- COMPUTING NODES ---

    comp_queues = []

    def failure_time(_n):
        if node_failure_times and len(node_failure_times) > _n:
            return node_failure_times[_n]
        return None

    for n in xrange(num_computing_nodes):

        comp_dir = path.join(data_dir, COMPUTING_NODE_KIND + str(n))
        comp_queue_in, comp_queue_out = Queue(), Queue()
        comp_failure_time = failure_time(n)

        comp_proc = multiprocessing.Process(
            target=run_computing_node,
            args=(comp_queue_out, comp_queue_in,
                  comp_dir, req_address, comp_failure_time)
        )
        comp_proc.start()

        processes.append(comp_proc)
        comp_queues.append((comp_queue_out, comp_queue_in))

    def shutdown():
        req_queue_out.put(MSG_STOP)
        for q, _ in comp_queues:
            q.put(MSG_STOP)

    # Wait until timeout elapses, the task is computed or an exception occurs
    result = None
    start_time = time.time()

    try:
        while True:

            req_msg = queue_get(req_queue_in)

            if req_msg == MSG_DONE:
                result = "Computation finished in {}s".format(time.time() - start_time)
            elif time.time() - start_time > timeout:
                result = "Computation timed out after {}s".format(timeout)
            else:
                for i, queues in enumerate(comp_queues):
                    comp_queue = queues[1]
                    comp_msg = queue_get(comp_queue)

                    if isinstance(comp_msg, Exception):
                        result = "Node failure [{}]: {}".format(i, comp_msg)
                    elif comp_msg:
                        report(COMPUTING_NODE_KIND, "{} reported: {}".format(i, comp_msg))
            if result:
                report("RESULT", result)
                break

            time.sleep(1.)

    except KeyboardInterrupt:
        result = "Test interrupted"
    except Exception as exc:
        result = "Exception occurred: {}".format(exc)
    finally:
        print "Shutting down nodes..."
        shutdown()
        for proc in processes:
            proc.join()
        shutil.rmtree(data_dir)
        return result
