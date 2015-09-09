import sys

from PyQt4.QtGui import QApplication, QDialog
from PyQt4.QtCore import QTimer
from threading import Lock

from golem.ui.manager import NodesManagerWidget
from golem.ui.uicustomizer import ManagerUiCustomizer, NodeDataState
from NodeStateSnapshot import NodeStateSnapshot
from networksimulator import GLOBAL_SHUTDOWN, LocalNetworkSimulator
from NodesManagerLogic import NodesManagerLogicTest, EmptyManagerLogic
from server.NodesManagerServer import NodesManagerServer

#FIXME: potencjalnie mozna tez spiac ze soba managery i wtedy kontrolowac zdalnie wszystkie koncowki i sobie odpalac nody w miare potrzeb, ale to nie na najblizsza prezentacje zabawa
class NodesManager:

    ########################
    def __init__(self, managerLogic = None, port = 20301):
        self.app = QApplication(sys.argv)
        self.mainWindow = NodesManagerWidget(None)
        self.uic = ManagerUiCustomizer(self.mainWindow, self)
        self.timer = QTimer()
        self.timer.timeout.connect(self.polledUpdate)
        self.lock = Lock()
        self.statesBuffer = []
        self.managerLogic = managerLogic

        self.uic.enableDetailedView(False)

        self.managerServer = NodesManagerServer(self, port)

         #FIXME: some shitty python magic
    def closeEvent_(self, event):
        try:
            self.managerLogic.getReactor().stop()
            self.managerLogic.terminateAllNodes()
        except Exception as ex:
            pass
        finally:
            GLOBAL_SHUTDOWN[ 0 ] = True
            event.accept()

        setattr(self.mainWindow.window.__class__, 'closeEvent', closeEvent_)

     ########################
    def setManagerLogic(self, managerLogic):
        self.managerLogic = managerLogic

    ########################
    def curSelectedNode(self):
        return None

    ########################
    def appendStateUpdate(self, update):
        with self.lock:
            self.statesBuffer.append(update)

    ########################
    def polledUpdate(self):
        with self.lock:
            for ns in self.statesBuffer:
                self.updateNodeState(ns)

            self.statesBuffer = []

    ########################
    def execute(self, usingqt4Reactor = False):
        self.mainWindow.show()
        self.timer.start(100)
        if not usingqt4Reactor:
            sys.exit(self.app.exec_())

    ########################
    def updateNodeState(self, ns):
        assert isinstance(ns, NodeStateSnapshot)

        tcss = ns.get_taskChunkStateSnapshot()

        ndslt = {}
        for sp in tcss.values():
            ndslt[ sp.getChunkId() ] = {    "chunkProgress" : sp.get_progress(),
                                            "cpu_power" : "{}".format(sp.getCpuPower()),
                                            "timeLeft" : "{}".format(sp.getEstimatedTimeLeft()),
                                            "cshd" : sp.getChunkShortDescr()
                                        }

        ndscs = {}

        ltss = ns.get_local_task_state_snapshot()
        for sp in ltss.values():
            ndscs[ sp.get_task_id() ] = {   "taskProgress" : sp.get_progress(),
                                            "allocTasks" : "{}".format(sp.get_total_tasks()),
                                            "allocChunks" : "{}".format(sp.get_total_chunks()),
                                            "activeTasks" : "{}".format(sp.get_active_tasks()),
                                            "activeChunks" : "{}".format(sp.get_active_chunks()),
                                            "chunksLeft" : "{}".format(sp.get_chunks_left()),
                                            "ltshd" : sp.get_task_short_desc()
                                       }

        ep = "{}:{}".format(ns.endpointAddr, ns.endpointPort)
        ts = ns.getFormattedTimestamp()
        pn = "{}".format(ns.getPeersNum())
        tn = "{}".format(ns.get_tasks_num())
        lm = ""
        if len(ns.getLastNetworkMessages()) > 0:
            lm = ns.getLastNetworkMessages()[-1][ 0 ] + str(ns.getLastNetworkMessages()[-1][ 4 ])


        ir = ns.is_running()

        node_data_state = NodeDataState(ir, ns.uid, ts, ep, pn, tn, lm, ndscs, ndslt)

        self.uic.UpdateNodePresentationState(node_data_state)

    ########################
    def runAdditionalNodes(self, numNodes):
        self.managerLogic.runAdditionalNodes(numNodes)

    ########################
    def runAdditionalLocalNodes(self, uid, numNodes):
        self.managerLogic.runAdditionalLocalNodes(uid, numNodes)

    ########################
    def terminate_node(self, uid):
        self.managerLogic.terminate_node(uid)

    ########################
    def terminateAllNodes(self):
        self.managerLogic.terminateAllNodes()

    ########################
    def terminateAllLocalNodes(self, uid):
        self.managerLogic.terminateAllLocalNodes(uid)

    ########################
    def loadTask(self, uid, filePath):
        self.managerLogic.loadTask(uid, filePath)

    ########################
    def enqueue_new_task(self, uid, w, h, numSamplesPerPixel, file_name):
        self.managerLogic.enqueue_new_task(uid, w, h, numSamplesPerPixel, file_name)

if __name__ == "__main__":

    manager = NodesManager()

    numNodes = 1
    maxLocalTasks = 2
    maxRemoteTasks = 30
    maxLocTaskDuration = 10.0
    maxRemTaskDuration = 28.0
    maxInnerUpdateDelay = 2.0
    nodeSpawnDelay = 1.0

    simulator = LocalNetworkSimulator(manager, numNodes, maxLocalTasks, maxRemoteTasks, maxLocTaskDuration, maxRemTaskDuration, maxInnerUpdateDelay, nodeSpawnDelay)
    manager.setManagerLogic(NodesManagerLogicTest(simulator))
    simulator.start()

    manager.execute()
