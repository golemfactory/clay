import os
from threading import Thread, Lock
import shutil
import logging

from golem.task.TaskBase import Task
from golem.resource.Resource import TaskResourceHeader, decompressDir
from golem.task.TaskComputer import PyTestTaskThread

from RenderingDirManager import getTestTaskPath, getTestTaskDirectory, getTestTaskTmpPath

logger = logging.getLogger(__name__)

class TaskTester:
    #########################
    def __init__( self, task, rootPath, finishedCallback ):
        assert isinstance( task, Task )
        self.task               = task
        self.testTaskResPath    = None
        self.tmpDir             = None
        self.success            = False
        self.lock               = Lock()
        self.tt                 = None
        self.rootPath           = rootPath
        self.finishedCallback   = finishedCallback

    #########################
    def run( self ):
        try:
            success = self.__prepareResources()
            self.__prepareTmpDir()

            if not success:
                return False

            ctd = self.task.queryExtraDataForTestTask()


            self.tt = PyTestTaskThread(  self,
                                ctd.subtaskId,
                                ctd.workingDirectory,
                                ctd.srcCode,
                                ctd.extraData,
                                ctd.shortDescription,
                                self.testTaskResPath,
                                self.tmpDir )
            self.tt.start()

        except Exception as exc:
            logger.warning( "Task not tested properly: {}".format( exc ) )
            self.finishedCallback( False )

    #########################
    def getProgress( self ):
        if self.tt:
            with self.lock:
                if self.tt.getError():
                    logger.warning( "Task not tested properly" )
                    self.finishedCallback( False )
                    return 0
                return self.tt.getProgress()
        return None

    #########################
    def __prepareResources( self ):

        self.testTaskResPath = getTestTaskPath( self.rootPath )
        if not os.path.exists( self.testTaskResPath ):
            os.makedirs( self.testTaskResPath )
        else:
            shutil.rmtree( self.testTaskResPath, True )
            os.makedirs( self.testTaskResPath )

        self.testTaskResDir = getTestTaskDirectory( )
        rh = TaskResourceHeader( self.testTaskResDir )
        resFile = self.task.prepareResourceDelta( self.task.header.taskId, rh )

        if resFile:
            decompressDir( self.testTaskResPath, resFile )

        return True
    #########################
    def __prepareTmpDir( self ):

        self.tmpDir = getTestTaskTmpPath( self.rootPath )
        if not os.path.exists( self.tmpDir ):
            os.makedirs( self.tmpDir )
        else:
            shutil.rmtree( self.tmpDir, True )
            os.makedirs( self.tmpDir )

    ###########################
    def taskComputed( self, taskThread ):
        if taskThread.result:
            res, estMem = taskThread.result
        if taskThread.result and res:
            logger.info( "Test task computation success !" )
            self.finishedCallback( True, estMem )
        else:
            logger.warning( "Test task computation failed !!!" )
            self.finishedCallback( False )