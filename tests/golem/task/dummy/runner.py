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
import thread
from twisted.internet import reactor


config_file = path.join(path.dirname(__file__), 'logging.ini')
logging.config.fileConfig(config_file, disable_existing_loggers = False)


def start_requesting_node():
    client = start_client()

    params = DummyTaskParameters(1024, 2048, 256, 0x0001ffff)
    task = DummyTask(client.get_node_name(), params, 3)
    client.enqueue_new_task(task)

    return client, task


def start_computing_node(peer_address):

    class DummyEnvironment(Environment):
        @classmethod
        def get_id(cls):
            return "DUMMY"

    client = start_client()

    dummy_env = DummyEnvironment()
    dummy_env.accept_tasks = True
    client.environments_manager.add_environment(dummy_env)

    client.connect(peer_address)


def monitor_task(requester, task, computer_process):
    import time
    import sys
    logger = logging.getLogger('dummy monitor')
    done = False
    while not done:
        if task.finished_computation():
            logger.info('Dummy task finished, closing down in 10 s')
            # we'll give the client some time for performing transactions etc.
            done = True
        else:
            logger.info('Dummy task still not finished')
        time.sleep(10)

    requester.stop_network()
    reactor.stop()

    computer_process.kill()
    sys.exit(0)


if len(sys.argv) > 1:
    # I'm a computing node
    start_computing_node(TCPAddress.parse(sys.argv[1]))
    reactor.run()

else:
    # I'm a requesting node
    requester, task = start_requesting_node()
    requester_addr = "{}:{}".format(
        requester.node.prv_addr, requester.node.prv_port)

    # Start the computing node in a separate process
    pythonpath = "".join(dir + ":" for dir in sys.path)
    env = {"PYTHONPATH": pythonpath}
    subproc = subprocess.Popen(["python", __file__, requester_addr], env = env)

    # Wait for the task completion and stop the requesting node
    thread.start_new_thread(monitor_task, (requester, task, subproc))

    reactor.run()

