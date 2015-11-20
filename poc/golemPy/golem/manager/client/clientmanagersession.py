
from golem.network.transport.message import MessagePeerStatus, MessageKillNode, MessageNewTask, MessageKillAllNodes, \
    MessageNewNodes
from golem.manager.managerconnstate import ManagerConnState
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
                self.client.add_new_task(task)

        elif type == MessageKillNode.Type:
            self.dropped()
            time.sleep(0.5)
            os.system("taskkill /PID {} /F".format(os.getpid()))

        elif type == MessageKillAllNodes.Type:
            process_service = ProcessService()
            if process_service.lock_state():
                pids = process_service.state.keys()
                logger.debug("Active processes with pids: {}".format(pids))
                process_service.unlock_state()

            cur_pid = os.getpid()
            if cur_pid in pids:
                pids.remove(cur_pid)

            logger.debug("Killing processes with pids: {}".format(pids))
            for pid in pids:
                os.system("taskkill /PID {} /F".format(pid))
            os.system("taskkill /PID {} /F".format(cur_pid))

        elif type == MessageNewNodes.Type:
            num = msg.num
            if self.client:
                self.client.run_new_nodes(num)


        else:
            logger.error("Wrong message received {}".format(msg))

    ##########################
    def send_client_state_snapshot(self, snapshot):
        if self.conn and self.conn.opened:
            self.conn.send_message(MessagePeerStatus(snapshot.uid, pickle.dumps(snapshot)))


class ClientManagerSessionFactory(object):
    def get_session(self, conn):
        return ClientManagerSession(conn)
