# Test script for running a single instance of a dummy task.
# The task simply computes hashes of some random data and requires
# no external tools. The amount of data processed (ie hashed) and computational
# difficulty is configurable, see comments in DummyTaskParameters.

from task import DummyTask, DummyTaskParameters
from golem.client import start_client

import logging.config
from os import path
import thread
from twisted.internet import reactor

config_file = path.join(path.dirname(__file__), 'logging.ini')
logging.config.fileConfig(config_file, disable_existing_loggers = False)

client = start_client()

params = DummyTaskParameters(1024, 2048, 256, 0x0001ffff)
task = DummyTask(client.get_node_name(), params, 3)
client.enqueue_new_task(task)


def monitor():
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
    # how to stop the client gracefully?
    logger.info('Stopping the client...')
    client.stop_network()
    reactor.stop()
    logger.info('Bye')
    sys.exit(0)


thread.start_new_thread(monitor, ())

reactor.run()
