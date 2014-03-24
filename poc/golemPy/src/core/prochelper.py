import os
import psutil
import fnmatch
import filelock
import time

from simpleserializer import SimpleSerializer
from simpleenv import SimpleEnv

DEFAULT_PROC_FILE = "node_processes.ctl"


class ProcessService:

    #################################
    def __init__( self, ctlFileName = DEFAULT_PROC_FILE ):

        ctlFile = SimpleEnv.envFileName( ctlFileName )

        self.maxFileSize = 1024 * 1024
        self.fd = -1
        self.ctlFile = ctlFile
        self.state = {}

        if not os.path.exists( ctlFile ) or os.path.getsize( ctlFile ) < 2:
            if self.__acquireLock():
                self.__writeStateSnapshot()

    #################################
    def __acquireLock( self, flags = os.O_EXCL ):
        flags |= os.O_EXCL | os.O_RDWR

        try:
            if not os.path.exists( self.ctlFile ):
                flags |= os.O_CREAT

            self.fd = os.open( self.ctlFile, flags )

            return True
        except Exception as ex:
            print "Failed to acquire lock due to {}".format( ex )
            return False

    #################################
    def __releaseLock( self ):
        if self.fd > 0:
            os.close( self.fd )
            self.fd = -1

    #################################
    def __readStateSnapshot( self ):
        os.lseek( self.fd, 0, 0 )
        data = os.read( self.fd, self.maxFileSize )
        self.state = SimpleSerializer.loads( data )

    #################################
    def __writeStateSnapshot( self ):
        data = SimpleSerializer.dumps( self.state )

        os.lseek( self.fd, 0, 0 )

        #FIXME: one hell of a hack but its pretty hard to truncate a file on Windows using low level API
        hack = os.fdopen( self.fd, "w" )
        hack.truncate( len( data ) )
        os.write( self.fd, data )

        hack.close()

    #################################
    def lockState( self ):
        if self.__acquireLock():
            self.__readStateSnapshot()
            return True
            
        return False

    #################################
    def unlockState( self ):
        if self.fd > 0:
            self.__writeStateSnapshot()
     
    #################################
    def __updateState( self ):
        pids = psutil.pids()
        updatedState = {}
        ids = []

        for p in self.state:
            if int( p ) in pids:
                updatedState[ p ] = self.state[ p ]
                ids.append( self.state[ p ][ 1 ] ) #localId    
            else:
                print "Process PID {} is inactive - removing".format( p )

        self.state = updatedState

        if len(ids) > 0:
            sids = sorted( ids, key = int )
            for i in range(len(sids)):
                if i < sids[ i ]:
                    return i

        return len(ids)

    #################################
    def registerSelf( self, extraData = None ):
        spid = int( os.getpid() )
        timestamp = time.time()

        if self.lockState():
            id = self.__updateState()
            self.state[ spid ] = [ timestamp, id, extraData ]
            self.unlockState()
            print "Registering new process - PID {} at time {} at location {}".format( spid, timestamp, id )

            return id

        return -1

    #################################
    def listAll( self, filter = None ):
        retList = []

        if not filter:
            filter = "*"

        for p in psutil.process_iter():
            if fnmatch.fnmatch( p.__str__(), filter ):
                retList.append( p )

        return retList

if __name__ == "__main__":

    ps = ProcessService( "test_ctl.ctl" )
    #print os.getpid()

    #for p in ps.listAll( filter = "*python.exe*"):
    #    print p

    import random

    id = ps.registerSelf()
    print "Registered id {}".format( id )
    time.sleep( 5.0 + 10.0 * random.random() )
