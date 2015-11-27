import subprocess
from PyQt4.QtCore import QObject
from PyQt4.QtNetwork import QTcpServer, QHostAddress


class TcpManagerLogic(QObject):

    def __init__(self, port):
        super(TcpManagerLogic, self).__init__()

        self.tcp_server = QTcpServer(self)
        self.tcp_server.listen(QHostAddress("0.0.0.0"), port)
        self.connect(self.tcp_server, SIGNAL("newConnection()"), self.add_connection)
        self.connections = []
        self.msg_buffers = []

    def add_connection(self):
        conn = self.tcp_server.nextPendingConnection()
        conn.nextBlockSize = 0
        self.connections.append(conn)

        self.connect(conn, signal("readyRead()"), self.recv_msg)
        self.connect(conn, signal("disconnected()"), self.disconnected)
        self.connect(conn, signal("error()"), self.error)

    def recv_msg(self):
        print

    def disconnected(self):
        for c in self.connections:
            pass

    def error(self):
        print

    def run_additional_nodes(self, num_nodes):
        for i in range(num_nodes):
            self.pc = subprocess.Popen(["python", "clientmain.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def terminate_node(self, uid):
        pass

    def terminate_all_nodes(self):
        pass

    def enqueue_new_task(self, uid, w, h, num_samples_per_pixel, file_name):
        pass
