import os
import sys
import glob
import cPickle as pickle
import zlib
import zipfile
import subprocess
import win32process

def formatVRayCmd( cmdFile, startTask, endTask, totalTasks, outfilebasename, scenefile, width, height, rtEngine ):
    print "formatVRayCMD"
    cmd = '"{}" -imgFile="{}\\chunk{}.exr" -sceneFile="{}" -imgWidth={} -imgHeight={} -region={};{};{};{} -autoClose=1 -display=0 -rtEngine={}'.format(cmdFile, outfilebasename, startTask, scenefile, width, height, 0, (startTask-1) * (height / totalTasks), width, startTask * ( height / totalTasks ), rtEngine )
    print cmd
    return cmd

def __readFromEnvironment( ):
    GOLEM_ENV = 'GOLEM'
    path = os.environ.get( GOLEM_ENV )
    if not path:
        print "No Golem environment variable found... Assuming that exec is in working folder"
        return 'vray.exe'

    sys.path.append( path )

    from examples.gnr.RenderingEnvironment import VRayEnvironment
    env = VRayEnvironment()
    cmdFile = env.getCmdPath()
    if cmdFile:
        return cmdFile
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        return 'vray.exe'


############################
def runVRayTask( pathRoot, startTask, endTask, totalTasks, outfilebasename, sceneFile, width, height, rtEngine):
    print 'runVray Taskk'
    outputFiles = tmpPath

    files = glob.glob( outputFiles + "*.exr" )

    for f in files:
        os.remove(f)

    print "sceneFile " + sceneFile
    if os.path.splitext( sceneFile )[1] == '.zip':
        with zipfile.ZipFile( sceneFile , "r" ) as z:
            z.extractall( os.getcwd() )
        sceneFile = glob.glob( "*.vrscene" )[0]


    cmdFile = __readFromEnvironment( )
    print "cmdFile " + cmdFile
    if os.path.exists( sceneFile ):
        cmd = formatVRayCmd( cmdFile, startTask, endTask, totalTasks, outputFiles, sceneFile, width, height, rtEngine )
    else:
        print "Scene file does not exist"
        return []

    print cmd

    pc = subprocess.Popen( cmd )

    win32process.SetPriorityClass( pc._handle, win32process.IDLE_PRIORITY_CLASS )


    pc.wait()

    files = glob.glob( outputFiles + "\*.exr" )

    res = []

    for f in files:
        fh = open( f, "rb" )
        fileData = fh.read()
        fileData = zlib.compress( fileData, 9 )
        res.append( pickle.dumps( ( os.path.basename( f ), fileData ) ) )
        fh.close()

    return res


output = runVRayTask ( pathRoot, startTask, endTask, totalTasks, outfilebasename, sceneFile, width, height, rtEngine )
