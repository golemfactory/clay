import zerorpc
from threading import Thread, Lock
import cPickle as pickle
import logging

logger = logging.getLogger(__name__)

def _local_tcp_addr(port):
    return "tcp://127.0.0.1:{}".format(port)

class SnapshotGetter:
    def __init__(self, client):
        self.client = client
        self.otherNodes = {}
        self.lock = Lock()

    def send_node_port(self, port):
        try:
            node = zerorpc.Client()
            node.connect(_local_tcp_addr(port))
            with self.lock:
                self.otherNodes[ port ] = node
        except:
            logger.error("Can't connect to port: {}".format(port))

    def send_snapshot(self):
        messages = []
        with self.lock:
            for port, node in self.otherNodes.items():
                try:
                    messages += pickle.loads(node.send_snapshot())
                except:
                    del self.otherNodes[port]

        with self.client.snapshot_lock:
            snapshot = self.client.last_node_state_snapshot
        messages.append(snapshot)
        try:
            messages = pickle.dumps(messages)
            return { 'data': messages, 'result_type': 0 }
        except Exception as ex:
            logger.error("Can't serialize snapshots: {}".format(str(ex)))



class InfoServer(Thread):
    def __init__(self, client, main_port, start_port, end_port):
        Thread.__init__(self)
        self.client = client
        self.daemon = True
        self.main_port = main_port
        self.start_port = start_port
        self.end_port = end_port
        self.server = None

    def __bind_port(self, port):
        self.server.bind(_local_tcp_addr(port))

    def __connect_to_main_port(self):
        try:
            self.__bind_port(self.main_port)
            return True
        except Exception as ex:
            logger.info(" Can't connect with port {}: {}".format(self.main_port, str(ex)))
            return False

    def __connect_to_additional_ports(self):
        info_client = None
        for port in range(self.start_port, self.end_port):
            try:
                self.__bind_port(port)
                info_client = zerorpc.Client()
                info_client.connect(_local_tcp_addr(self.main_port))
                info_client.send_node_port(port)
                break
            except:
                pass
        if info_client:
            return True
        else:
            return False


    def run(self):
        self.server = zerorpc.Server(SnapshotGetter(self.client))
        if not self.__connect_to_main_port():
            if not self.__connect_to_additional_ports():
                logger.error("Info server not connnected")
                return
        self.server.run()

