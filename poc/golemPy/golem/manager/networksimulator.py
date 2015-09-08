from threading import Thread, Lock
import time
import random
import logging

from PyQt4 import QtCore

from NodeStateSnapshot import NodeStateSnapshot, LocalTaskStateSnapshot, TaskChunkStateSnapshot

logger = logging.getLogger(__name__)

GLOBAL_SHUTDOWN = [ False ]

class NodeSimulator(QtCore.QThread):

    #updateRequest = QtCore.pyqtSignal()

    ########################
    def __init__(self, simulator, id, uid, numLocalTasks, numRemoteTasks, localTaskDuration, remoteTaskDuration, innerUpdateDelay):
        super(NodeSimulator, self).__init__()
            
        self.simulator = simulator
        self.id = id
        self.uid = uid
        self.numLocalTasks = numLocalTasks
        self.numRemoteTasks = numRemoteTasks
        self.localTaskDuration = localTaskDuration
        self.remoteTaskDuration = remoteTaskDuration
        self.startTime = time.time()
        self.innerUpdateDelay = innerUpdateDelay
        
        self.locProgress = 0.0
        self.remProgress = 0.0

        self.forcedQuit = False

        self.localAddr = "127.0.0.1"
        self.localPort = int(random.random() * 60000.0 + 1024.0)
        self.peersNum = 0
        self.tasksNum = 0
        self.running = True
        
        self.addedTasks = []

        for i in range(numLocalTasks):
            self.addedTasks.append("Uninteresting taks desc {}".format(i))

    ########################
    def terminate(self):
        self.forcedQuit = True

    ########################
    def enqueueTask(self, w, h, numSamplesPerPixel, file_name):
        self.numLocalTasks += 1
        self.totalDuration += self.localTaskDuration
        extra_data = "w: {}, h: {}, spp: {}, file: {}".format(w, h, numSamplesPerPixel, file_name)

        self.addedTasks.append(extra_data)

    ########################
    def getId(self):
        return self.id

    ########################
    def getUid(self):
        return self.uid

    ########################
    def getStateSnapshot(self):
        add_peers = 1 if random.random() >= 0.45 else -1

        self.peersNum += add_peers

        if self.peersNum < 0:
            self.peersNum = 0
        if self.peersNum > 10:
            self.peersNum = 10

        add_tasks = 1 if random.random() >= 0.5 else -1

        self.tasksNum += add_tasks

        if self.tasksNum < 0:
            self.tasksNum = 0
        if self.tasksNum > 200:
            self.tasksNum = 200

        cur_time = time.time()

        ctl = self.remoteTaskDuration - (cur_time - self.remTaskStartTime)
        ctl = max(0.0, ctl)
        tcss = TaskChunkStateSnapshot('0xbaadf00d', 1600.0, ctl, self.remProgress, "chunk data: {}".format(self.remTask))

        allChunks = 1000 * 1000

        totalTasks = int(1000.0 * self.locProgress)
        totalChunks = 1000 * totalTasks
        
        activeRandom = random.random()
        activeTasks = int(activeRandom * totalTasks)
        activeChunks = int(activeRandom * totalChunks)

        descr = "nothing here"
        lcT = self.locTask

        if lcT < len(self.addedTasks):
            descr = self.addedTasks[ lcT ]

        ltss = LocalTaskStateSnapshot('0xcdcdcdcd', totalTasks, totalChunks, activeTasks, activeChunks, allChunks - totalChunks, self.locProgress, descr)

        return NodeStateSnapshot(self.running, self.uid, self.peersNum, self.tasksNum, self.localAddr, self.localPort, ['test message {}'.format(random.randint(0,200))], ['test message {}'.format(random.randint(10, 70))], { '0' : tcss }, { '0xcdcdcd' : ltss })

    ########################
    def run(self):

        startTime = time.time()
        self.locTasksDuration = self.numLocalTasks * self.localTaskDuration
        self.remTasksDuration = self.numRemoteTasks * self.remoteTaskDuration

        self.totalDuration = max(self.locTasksDuration, self.remTasksDuration)

        self.locTask = 0
        self.locTaskStartTime = startTime
        self.remTask = 0
        self.remTaskStartTime = startTime

        logger_msg = "Starting node '{}' local tasks: {} remote tasks: {}".format(self.uid, self.numLocalTasks, self.numRemoteTasks)
        logger.info("{} ->local task dura: {} secs, remote task dura: {} secs".format(logger_msg, self.localTaskDuration, self.remoteTaskDuration))

        while time.time() - startTime < self.totalDuration:
                
            if GLOBAL_SHUTDOWN[ 0 ]:
                logger.warning("{}: Global shutdown triggered - bailing out".format(self.uid))
                break

            if self.forcedQuit:
                logger.warning("{}: Forced quit triggered - bailing out".format(self.uid))
                break

            time.sleep(self.innerUpdateDelay)

            cur_time = time.time()

            if self.locTask < self.numLocalTasks:
                dt = cur_time - self.locTaskStartTime

                if dt <= self.localTaskDuration:
                    self.locProgress = dt / self.localTaskDuration
                else:
                    self.locTaskStartTime = cur_time
                    self.locTask += 1
                    self.locProgress = 0.0

            if self.remTask < self.numRemoteTasks:
                dt = cur_time - self.remTaskStartTime

                if dt <= self.remoteTaskDuration:
                    self.remProgress = dt / self.remoteTaskDuration
                else:
                    self.remTaskStartTime = cur_time
                    self.remTask += 1
                    self.remProgress = 0.0

            self.simulator.updateRequested(self.id)
            #self.updateRequest.emit()
            #self.emit(QtCore.SIGNAL("Activated()"),self.dupa, QtCore.Qt.QueuedConnection)
            #print "\r                                                                      ",
            #print "\r{:3} : {}   {:3} : {}".format(locTask, self.locProgress, remTask, self.remProgress),

        logger.info("Finished node '{}'".format(self.uid))
        
        if self.running:
            self.running = False
            self.simulator.updateRequested(self.id)

class LocalNetworkSimulator(Thread):

    ########################
    def __init__(self, manager, numNodes, maxLocalTasks, maxRemoteTasks, maxLocalTaskDuration, maxRemoteTaskDuration, maxInnerUpdateDelay, nodeSpawnDelay):
        super(LocalNetworkSimulator, self).__init__()

        self.manager = manager
        self.numNodes = numNodes
        self.maxLocTasks = maxLocalTasks
        self.maxRemTasks = maxRemoteTasks
        self.maxLocTaskDura = maxLocalTaskDuration
        self.maxRemTaskDura = maxRemoteTaskDuration
        self.maxInnerUpdateDelay = maxInnerUpdateDelay
        self.nodeSpawnDelay = nodeSpawnDelay
        self.curNode = 0
        self.lock = Lock()

        self.nodes = []

    ########################
    def terminateAllNodes(self):
        with self.lock:
            for node in self.nodes:
                node.terminate()

    ########################
    def terminateNode(self, uid):
        with self.lock:
            for i, node in enumerate(self.nodes):
                if node.getUid() == uid:
                    node.terminate()
                    #self.nodes.pop(i)
                    break

    ########################
    def enqueueNodeTask(self, uid, w, h, numSamplesPerPixel, file_name):
        with self.lock:
            for node in self.nodes:
                if node.getUid() == uid:
                    node.enqueueTask(w, h, numSamplesPerPixel, file_name)

    ########################
    def addNewNode(self):
        with self.lock:
            node = self.createNewNode(self.curNode)
            self.nodes.append(node)
            node.start()
            self.curNode += 1
            #node.updateRequest.connect(self.updateRequested)

    ########################
    def updateRequested(self, id):
        self.manager.appendStateUpdate(self.nodes[ id ].getStateSnapshot())

    ########################
    def getRandomizedUp(self, value, scl = 1.4):
        return (0.1 +  scl * random.random()) * value

    ########################
    def getRandomizedDown(self, value, scl = 0.7):
        return (1.0 - random.random() * scl) * value

    ########################
    def createNewNode(self, id):
        uid = "gen - uid - {}".format(id)
        numLocTasks = int(self.getRandomizedDown(self.maxLocTasks))
        numRemTasks = int(self.getRandomizedDown(self.maxRemTasks))
        locTaskDura = self.getRandomizedDown(self.maxLocTaskDura)
        remTaskDura = self.getRandomizedDown(self.maxRemTaskDura)
        updateDelay = self.getRandomizedDown(self.maxInnerUpdateDelay)

        return NodeSimulator(self, id, uid, numLocTasks, numRemTasks, locTaskDura, remTaskDura, updateDelay)

    ########################
    def run(self):
        time.sleep(1) #just out of decency

        cur_time = time.time()

        logger.info("Starting node simulator for {} nodes".format(self.numNodes))

        while not GLOBAL_SHUTDOWN[ 0 ]:

            if self.curNode < self.numNodes:
                self.addNewNode()

            time.sleep(self.getRandomizedUp(self.nodeSpawnDelay))

        logger.info("Local network simulator finished running.")
        logger.info("Waiting for nodes to finish")

        #10 seconds should be just enough for each node to do its cleanup
        for node in self.nodes:
            node.wait()

        logger.info("Simulation finished")
