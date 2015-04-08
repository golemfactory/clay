import zerorpc

import logging

logger = logging.getLogger( __name__ )

def _localTcpAddr( port ):
    print "port {}".format( port )
    return "tcp://0.0.0.0:{}".format( port )


class TaskAdder():
    def __init__(self ):
        self.taskList = []

    def getTasks(self):
        list = self.taskList
        self.taskList = []
        return list

    def addTask(self, task):
        self.taskList.append( task )

class TaskAdderServer:
    def __init__( self, port ):
        self.port = port
        self.server = None

    def __bindPort(self, port ):
        self.server.bind( _localTcpAddr( port ) )

    def __connect(self):
        try:
            self.__bindPort( self.port )
            return True
        except Exception as ex:
            logger.warning("Plugin server can't connect with port {}: {}".format( self.port, str( ex ) ) )
            return False

    def run( self ):
        self.server = zerorpc.Server( TaskAdder() )
        if not self.__connect():
            print "not conneted"
            return
        print "server ruuuuuning"
        self.server.run()
        print "after server run"

def startTaskAdderServer(port):
    server = TaskAdderServer(port)
    server.run()


   # def stop(self):
    #    time.sleep(3)
    #    self.server.stop()