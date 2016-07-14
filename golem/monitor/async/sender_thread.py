import threading
import Queue

from golem.monitor.transport.sender import DefaultJSONSender as Sender


class SenderThread(threading.Thread):

    def __init__(self, meta_data, timeout, host, sender_timeout, proto_version):
        super(SenderThread, self).__init__()
        self.queue = Queue.Queue()
        self.stop_request = threading.Event()
        self.meta_data = meta_data
        self.timeout = timeout
        self.sender = Sender(host, sender_timeout, proto_version)

    def send(self, o):
        self.queue.put(o)

    def run(self):

        while not self.stop_request.isSet():
            try:
                msg = self.queue.get(True, self.timeout)
                self.sender.send(msg)
            except Queue.Empty:
                # send ping message
                self.sender.send(self.meta_data)

    def join(self, timeout=None):
        self.stop_request.set()
        super(SenderThread, self).join(timeout)
