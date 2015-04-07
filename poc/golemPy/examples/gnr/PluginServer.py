import zerorpc
import gevent
from threading import Thread, Event
import logging
import sys
import time

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

    def stop(self):
        self.stop()

class TaskAdderServer( Thread ):
    def __init__( self, port ):
        Thread.__init__( self )
        self.deamon = True
        self.port = port
        self.server = None
        self._stop = Event()

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

   # def stop(self):
    #    time.sleep(3)
    #    self.server.stop()