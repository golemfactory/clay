from golem.manager.nodesmanagerlogic import EmptyManagerLogic
from PyQt4.QtGui import QMessageBox
import time
import os
import subprocess
import logging
import pickle

logger = logging.getLogger(__name__)


def run_additional_nodes(path, num_nodes):
    for i in range(num_nodes):
        time.sleep(0.1)
        prev_path = os.getcwd()
        os.chdir(path)
        pc = subprocess.Popen(["python", "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        os.chdir(prev_path)


def run_manager(path):
    prev_path = os.getcwd()
    os.chdir(path)
    pc = subprocess.Popen(["python", "managerMain.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
    os.chdir(prev_path)


class GNRManagerLogic(EmptyManagerLogic):
    def __init__(self, manager_server, node_path):
        EmptyManagerLogic.__init__(self, manager_server)
        self.node_path = node_path

    def run_additional_nodes(self, num_nodes):
        run_additional_nodes("../gnr", num_nodes)

    def load_task(self, uid, file_path):
        try:
            f = open(file_path, 'r')
            definition = pickle.loads(f.read())
        except Exception as err:
            definition = None
            logger.error("Can't unpickle the file {}: {}".format(file_path, err))
            QMessageBox().critical(None, "Error", "This is not a proper gt file")
        finally:
            f.close()
        self.manager_server.send_new_task(uid, definition)

    def enqueue_new_task(self, uid, w, h, num_samples_per_pixel, file_name):
        pass

    def terminate_all_local_nodes(self, uid):
        self.manager_server.send_terminate_all(uid)

    def run_additional_local_nodes(self, uid, num_nodes):
        self.manager_server.send_new_nodes(uid, num_nodes)
