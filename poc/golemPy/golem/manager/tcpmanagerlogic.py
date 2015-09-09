import subprocess

from PyQt4.QtCore import QObject
from PyQt4.QtNetwork import QTcpServer, QHostAddress

class TcpManagerLogic(QObject):

    ########################
    def __init__(self, port):
        super(TcpManagerLogic,self).__init__()

        self.tcpServer = QTcpServer(self)
        self.tcpServer.listen(QHostAddress("0.0.0.0"), port)
        self.connect(self.tcpServer, SIGNAL("newConnection()"), self.addConnection)
        self.connections = []
        self.msgBuffers = []

    ########################
    def addConnection(self):
        conn = self.tcpServer.nextPendingConnection()
        conn.nextBlockSize = 0
        self.connections.append(conn)

        self.connect(conn, signal("readyRead()"), self.recvMsg)
        self.connect(conn, signal("disconnected()"), self.disconnected)
        self.connect(conn, signal("error()"), self.error)

    ########################
    def recvMsg(self):
        print

    ########################
    def disconnected(self):
        for c in self.connections:
            pass
            #if c.i

    ########################
    def error(self):
        print

    ########################
    def runAdditionalNodes(self, numNodes):
        for i in range(numNodes):
            self.pc = subprocess.Popen(["python", "clientmain.py"], creationflags = subprocess.CREATE_NEW_CONSOLE)

    ########################
    def terminate_node(self, uid):
        pass

    ########################
    def terminateAllNodes(self):
        pass

    ########################
    def enqueue_new_task(self, uid, w, h, numSamplesPerPixel, file_name):
        pass
