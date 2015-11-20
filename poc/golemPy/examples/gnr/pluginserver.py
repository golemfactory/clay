import zerorpc

import logging

logger = logging.getLogger(__name__)

def _local_tcp_addr(port):
    print "port {}".format(port)
    return "tcp://0.0.0.0:{}".format(port)


class TaskAdder():
    def __init__(self):
        self.task_list = []

    def get_tasks(self):
        list = self.task_list
        self.task_list = []
        return list

    def add_task(self, task):
        self.task_list.append(task)


class TaskAdderServer:
    def __init__(self, port):
        self.port = port
        self.server = None

    def __bind_port(self, port):
        self.server.bind(_local_tcp_addr(port))

    def __connect(self):
        try:
            self.__bind_port(self.port)
            return True
        except Exception as ex:
            logger.warning("Plugin server can't connect with port {}: {}".format(self.port, str(ex)))
            return False

    def run(self):
        self.server = zerorpc.Server(TaskAdder())
        if not self.__connect():
            print "not conneted"
            return
        print "server ruuuuuning"
        self.server.run()
        print "after server run"


def start_task_adder_server(port):
    server = TaskAdderServer(port)
    server.run()


   # def stop(self):
    #    time.sleep(3)
    #    self.server.stop()