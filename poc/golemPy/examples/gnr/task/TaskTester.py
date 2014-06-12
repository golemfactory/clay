import os
from golem.task.TaskBase import Task
from golem.task.resource.Resource import TaskResourceHeader, decompressDir
from golem.task.TaskComputer import PyTaskThread

class TaskTester:
    #########################
    def __init__( self, task ):
        assert isinstance( task, Task )
        self.task               = task
        self.testTaskResPath    = None
        self.tmpDir             = None
        self.success            = False

    def run( self ):
        success = self.__prepareResources()

        if not success:
            return False

        ctd = self.task.queryExtraDataForTestTask()


        tt = PyTaskThread( self,
                           ctd.subtaskId,
                           ctd.workingDirectory,
                           ctd.srcCode,
                           ctd.extraData,
                           ctd.shortDescr,
                           self.testTaskResPath,
                           self.tmpDir )
        tt.start()

    #########################
    def getSuccess( self ):
        return self.success

    #########################
    def __prepareResources( self ):

        self.testTaskResPath = "testing_task_resources"
        self.testTaskResPath = os.path.abspath( self.testTaskResPath )
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )
        else:
            os.removedirs( self.testTaskResPath )
            os.makedirs( self.testTaskResPath )

        rh = TaskResourceHeader( "testing_task_resources" )
        resFile = self.task.prepareResourceDelta( self.task.header.taskId, rh )

        if resFile:
            decompressDir( self.testTaskResPath, resFile )
        else:
            return False

    #########################
    def __prepareTmpDir( self ):
        self.tmpDir = "testing_task_tmp"
        self.tmpDir = os.path.abspath( self.tmpDir )
        if not os.path.exists( self.tmpDir ):
            os.makedirs( self.tmpDir )
        else:
            os.removedirs( self.tmpDir )
            os.makedirs( self.tmpDir )


    ###########################
    def taskComputed( self, taskThread ):
        if taskThread.result:
            print "Test task computation success !"
            self.success =  True
        else:
            print "Test task computation failed !!!"
            self.success = False