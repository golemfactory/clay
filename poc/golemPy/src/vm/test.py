from vm import PythonVM
from twisted.internet import task
from taskdistributor import g_taskDistributor
import time


class TaskPerformer:
    def __init__( self ):
        self.vm = PythonVM()
        self.workingTask = task.LoopingCall(self.__doWork)
        self.doWorkTask.start(0.1, False)

    def __chooseTask( self ):
        return self.tasks[ int( time.time() ) % len( self.tasks ) ]

    def __doWork( self ):
        self.tasks = g_taskDistributor.getFreeTasks()
        td = self.__chooseTask()
        t = g_taskDistributor.giveTask( t.id )
        if t:
            self.vm.runTask( t )
            g_taskDistributor.acceptTask( t )





def main():

    pass

main()