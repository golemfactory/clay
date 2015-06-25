import zerorpc
from threading import Thread, Lock
import cPickle as pickle
import logging

logger = logging.getLogger(__name__)

def _localTcpAddr(port):
    return "tcp://127.0.0.1:{}".format(port)

class SnapshotGetter:
    def __init__(self, client):
        self.client = client
        self.otherNodes = {}
        self.lock = Lock()

    def sendNodePort(self, port):
        try:
            node = zerorpc.Client()
            node.connect(_localTcpAddr(port))
            with self.lock:
                self.otherNodes[ port ] = node
        except:
            logger.error("Can't connect to port: {}".format(port))

    def sendSnapshot(self):
        messages = []
        with self.lock:
            for port, node in self.otherNodes.items():
                try:
                    messages += pickle.loads(node.sendSnapshot())
                except:
                    del self.otherNodes[port]

        with self.client.snapshotLock:
            snapshot = self.client.lastNodeStateSnapshot
        messages.append(snapshot)
        try:
            messages = pickle.dumps(messages)
            return { 'data': messages, 'resultType': 0 }
        except Exception as ex:
            logger.error("Can't serialize snapshots: {}".format(str(ex)))



class InfoServer(Thread):
    def __init__(self, client, mainPort, startPort, endPort):
        Thread.__init__(self)
        self.client = client
        self.daemon = True
        self.mainPort = mainPort
        self.startPort = startPort
        self.endPort = endPort
        self.server = None

    def __bindPort(self, port):
        self.server.bind(_localTcpAddr(port))

    def __connectToMainPort(self):
        try:
            self.__bindPort(self.mainPort)
            return True
        except Exception as ex:
            logger.info(" Can't connect with port {}: {}".format(self.mainPort, str(ex)))
            return False

    def __connectToAdditionalPorts(self):
        infoClient = None
        for port in range(self.startPort, self.endPort):
            try:
                self.__bindPort(port)
                infoClient = zerorpc.Client()
                infoClient.connect(_localTcpAddr(self.mainPort))
                infoClient.sendNodePort(port)
                break
            except:
                pass
        if infoClient:
            return True
        else:
            return False


    def run(self):
        self.server = zerorpc.Server(SnapshotGetter(self.client))
        if not self.__connectToMainPort():
            if not self.__connectToAdditionalPorts():
                logger.error("Info server not connnected")
                return
        self.server.run()

