from golem.manager.NodesManagerLogic import EmptyManagerLogic

from PyQt4.QtGui import QMessageBox

import time
import os
import subprocess
import logging
import pickle

logger = logging.getLogger(__name__)

def runAdditionalNodes(path,  numNodes):
    for i in range(numNodes):
        time.sleep(0.1)
        prevPath = os.getcwd()
        os.chdir(path)
        pc = subprocess.Popen(["python", "main.py"], creationflags = subprocess.CREATE_NEW_CONSOLE)
        os.chdir(prevPath)

def runManager(path):
    prevPath = os.getcwd()
    os.chdir(path)
    pc = subprocess.Popen([ "python", "managerMain.py" ], creationflags = subprocess.CREATE_NEW_CONSOLE)
    os.chdir(prevPath)



class GNRManagerLogic(EmptyManagerLogic):

    def __init__(self, managerServer, nodePath):
        EmptyManagerLogic.__init__(self, managerServer)
        self.nodePath = nodePath

    def runAdditionalNodes(self, numNodes):
        runAdditionalNodes("../gnr", numNodes)

    ########################
    def loadTask(self, uid, filePath):
        f = open(filePath, 'r')

        try:
            definition = pickle.loads(f.read())
        except Exception, e:
            definition = None
            logger.error("Can't unpickle the file {}: {}".format(filePath, str(e)))
            QMessageBox().critical(None, "Error", "This is not a proper gt file")
        finally:
            f.close()
        self.managerServer.sendNewTask(uid, definition)

    ########################
    def enqueueNewTask(self, uid, w, h, numSamplesPerPixel, fileName):
        pass

    ########################
    def terminateAllLocalNodes(self, uid):
        self.managerServer.sendTerminateAll(uid)

    ########################
    def runAdditionalLocalNodes(self, uid, numNodes):
        self.managerServer.sendNewNodes(uid, numNodes)

