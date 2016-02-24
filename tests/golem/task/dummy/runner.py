# Test script for running a single instance of a dummy task.
# The task simply computes hashes of some random data and requires
# no external tools. The amount of data processed (ie hashed) and computational
# difficulty is configurable, see comments in DummyTaskParameters.

from task import DummyTask, DummyTaskParameters
from golem.client import start_client
from golem.environments.environment import Environment
from golem.network.transport.tcpnetwork import TCPAddress

import logging.config
from os import path
import subprocess
import sys
import time
import thread
from twisted.internet import reactor


config_file = path.join(path.dirname(__file__), 'logging.ini')
logging.config.fileConfig(config_file, disable_existing_loggers = False)


def run_computing_node(peer_address):
    logger = logging.getLogger("ComputeNode")
    logger.info("<<< Starting compute node...")

    class DummyEnvironment(Environment):
        @classmethod
        def get_id(cls):
            return "DUMMY"

    client = start_client()

    dummy_env = DummyEnvironment()
    dummy_env.accept_tasks = True
    client.environments_manager.add_environment(dummy_env)

    logger.info("<<< Connecting to requester node at {}:{}".format(
        peer_address.address, peer_address.port))
    client.connect(peer_address)

    reactor.run()


def monitor_task(requester, task, computer_process, timeout = 120.0):
    logger = logging.getLogger('dummy monitor')

    done = False
    t0 = time.time()
    try:
        while not done:

            elapsed = time.time() - t0
            if elapsed >= timeout:
                raise RuntimeError("Task computation timed out")

            computer_process.poll()
            if computer_process.returncode:
                raise RuntimeError("Computer process exited")

            if task.finished_computation():
                logger.info('Dummy task finished, closing down in 5 s')
                # Give the client some time for performing transactions etc.
                done = True
            else:
                logger.info('Dummy task not finished yet ({} sec)'.format(
                    elapsed))
            time.sleep(5)
    finally:
        requester.stop_network()
        reactor.stop()

        if not computer_process.returncode:
            computer_process.kill()


def run_requesting_node():
    logger = logging.getLogger("RequestingNode")
    logger.info(">>> Starting requesting node...")

    client = start_client()

    params = DummyTaskParameters(1024, 2048, 256, 0x0001ffff)
    task = DummyTask(client.get_node_name(), params, 3)
    client.enqueue_new_task(task)

    port = client.p2pservice.cur_port
    requester_addr = "{}:{}".format(client.node.prv_addr, port)
    logger.info(">>> Requester node address: {}".format(requester_addr))

    # Start the computing node in a separate process
    pythonpath = "".join(dir + ":" for dir in sys.path)
    env = {"PYTHONPATH": pythonpath}
    subproc = subprocess.Popen(["python", __file__, requester_addr], env = env)

    # Wait for the task completion and stop the requesting node
    thread.start_new_thread(monitor_task, (client, task, subproc))

    reactor.run()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # I'm a computing node
        run_computing_node(TCPAddress.parse(sys.argv[1]))
    else:
        # I'm a requesting node
        run_requesting_node()
