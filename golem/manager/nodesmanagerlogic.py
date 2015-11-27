import subprocess
import time
import random
from golem.task.taskbase import TaskHeader


class NodesManagerLogicTest:
    def __init__(self, simulator):
        self.simulator = simulator

    def run_additional_nodes(self, num_nodes):
        for i in range(num_nodes):
            self.simulator.add_new_node()

    def terminate_node(self, uid):
        self.simulator.terminate_node(uid)

    def terminate_all_nodes(self):
        self.simulator.terminate_all_nodes()

    def enqueue_new_task(self, uid, w, h, num_samples_per_pixel, file_name):
        self.simulator.enqueue_node_task(uid, w, h, num_samples_per_pixel, file_name)


class EmptyManagerLogic:
    def __init__(self, manager_server):
        self.reactor = None
        self.manager_server = manager_server
        self.activeNodes = []

    def set_reactor(self, reactor):
        self.reactor = reactor
        self.manager_server.set_reactor(reactor)

    def get_reactor(self):
        return self.reactor

    def run_additional_nodes(self, num_nodes):
        for i in range(num_nodes):
            time.sleep(0.1)
            pc = subprocess.Popen(["python", "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.activeNodes.append(pc)

    def terminate_node(self, uid):
        self.manager_server.send_terminate(uid)

    def terminate_all_nodes(self):
        for node in self.manager_server.manager_sessions:
            try:
                self.manager_server.send_terminate(node.uid)
            except:
                logger.warning("Can't send terminate signal to node {}".format(node.uid))

    def enqueue_new_task(self, uid, w, h, num_samples_per_pixel, file_name):
        hash = random.getrandbits(128)
        th = TaskHeader(uid, "222222", "", 0)
        self.manager_server.send_new_task(uid,
                                          PbrtRenderTask(th, "", 32, 16, 2, "test_chunk_", "resources/city-env.pbrt"))
        # self.manager_server.send_new_task(uid, VRayTracingTask(w, h, num_samples_per_pixel, th, file_name))
