
from golem.network.transport.message import MessagePeerStatus, MessageNewTask, MessageKillNode, MessageKillAllNodes, MessageNewNodes
import cPickle as pickle
from golem.manager.ManagerConnState import ManagerConnState

import logging

logger = logging.getLogger(__name__)

class ServerManagerSession:

    ConnectionStateType = ManagerConnState

    ##########################
    def __init__(self, conn, address, port, server):
        self.conn       = conn
        self.server     = server
        self.address    = address
        self.port       = port
        self.uid        = None

    ##########################
    def dropped(self):
        self.conn.close()
        self.server.manager_session = None
        self.server.manager_session_disconnect(self.uid)

    ##########################
    def interpret(self, msg):

        type = msg.get_type()

        if type == MessagePeerStatus.Type:
            nss = pickle.loads(msg.data)
            self.uid = nss.get_uid()
            self.server.node_state_snapshot_received(nss)

        else:
            logger.error("Wrong message received {}".format(msg))

    ##########################
    def send_client_state_snapshot(self, snapshot):

        if self.conn and self.conn.opened:
            self.conn.send_message(MessagePeerStatus(snapshot.uid, pickle.dumps(snapshot)))

    def send_kill_node(self):
        if self.conn and self.conn.opened:
            self.conn.send_message(MessageKillNode())

    def send_kill_all_nodes(self):
        if self.conn and self.conn.opened:
            self.conn.send_message(MessageKillAllNodes())


    ##########################
    def send_new_task(self, task):
        if self.conn and self.conn.opened:
            tp = pickle.dumps(task)
            self.conn.send_message(MessageNewTask(tp))

    ##########################
    def send_new_nodes(self, num_nodes):
        if self.conn and self.conn.opened:
            self.conn.send_message(MessageNewNodes(num_nodes))

class ServerManagerSessionFactory:
    def __init__(self, server):
        self.server = server

    def get_session(self, conn):
        return ServerManagerSession(conn, self.server, '127.0.0.1', self.server.port)

if __name__ == "__main__":

    def main():
        from NodeStateSnapshot import NodeStateSnapshot

        snapshot  = NodeStateSnapshot("some uiid", 0.2, 0.7)
        d = pickle.dumps(snapshot)
        ud = pickle.loads(d)
        t = 0


    main()