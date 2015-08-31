
from golem.network.transport.message import MessagePeerStatus, MessageKillNode, MessageNewTask, MessageKillAllNodes, \
    MessageNewNodes
from golem.manager.ManagerConnState import ManagerConnState
from golem.core.prochelper import ProcessService

import cPickle as pickle
import time
import os
import logging

logger = logging.getLogger(__name__)

class ClientManagerSession:

    ConnectionStateType = ManagerConnState

    ##########################
    def __init__(self, conn):
        self.conn       = conn
        self.client     = None

    ##########################
    def dropped(self):
        self.conn.close()

    ##########################
    def interpret(self, msg):

        type = msg.get_type()

        if type == MessageNewTask.Type:
            task = pickle.loads(msg.data)
            if self.client:
                self.client.addNewTask(task)

        elif type == MessageKillNode.Type:
            self.dropped()
            time.sleep(0.5)
            os.system("taskkill /PID {} /F".format(os.getpid()))

        elif type == MessageKillAllNodes.Type:
            processService = ProcessService()
            if processService.lockState():
                pids = processService.state.keys()
                logger.debug("Active processes with pids: {}".format(pids))
                processService.unlockState()

            curPid = os.getpid()
            if curPid in pids:
                pids.remove(curPid)

            logger.debug("Killing processes with pids: {}".format(pids))
            for pid in pids:
                os.system("taskkill /PID {} /F".format(pid))
            os.system("taskkill /PID {} /F".format(curPid))

        elif type == MessageNewNodes.Type:
            num = msg.num
            if self.client:
                self.client.runNewNodes(num)


        else:
            logger.error("Wrong message received {}".format(msg))

    ##########################
    def sendClientStateSnapshot(self, snapshot):
        if self.conn and self.conn.opened:
            self.conn.sendMessage(MessagePeerStatus(snapshot.uid, pickle.dumps(snapshot)))


class ClientManagerSessionFactory:
    def get_session(self, conn):
        return ClientManagerSession(conn)
