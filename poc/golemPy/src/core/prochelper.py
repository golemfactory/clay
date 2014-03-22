import os
import psutil
import fnmatch
import filelock
import time
#DEBUG VERSION
import json
#RELEASE VERSION
#import pickle

class ProcessService:

    #################################
    def __init__( self, ctlFileName ):

        self.maxFileSize = 1024 * 1024
        self.fd = -1
        self.ctlFile = ctlFileName
        self.state = {}

        if not os.path.exists( ctlFileName ) or os.path.getsize( ctlFileName ) < 2:
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
        self.state = json.loads( data )

    #################################
    def __writeStateSnapshot( self ):
        data = json.dumps( self.state )

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

        print "STATE {}".format( self.state )
        for p in self.state:
            if int( p ) in pids:
                updatedState[ p ] = self.state[ p ]
            else:
                print "Process PID {} is inactive - removing".format( p )

        self.state = updatedState

    #################################
    def registerSelf( self, extraData = None ):
        spid = int( os.getpid() )
        timestamp = time.time()

        print "Registering new process with PID {} at timestamp {}".format( spid, timestamp )

        if self.lockState():
            self.__updateState()
            self.state[ spid ] = [ timestamp, extraData ]
            self.unlockState()

            return len( self.state ) - 1

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

    id = ps.registerSelf()
    print "Registered id {}".format( id )
    time.sleep( 10 )
