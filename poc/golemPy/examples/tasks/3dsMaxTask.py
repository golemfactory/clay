import os
import sys
import glob
import cPickle as pickle
import zlib
import subprocess
import win32process

def format3dsMaxCmd( cmdFile, startTask, endTask, totalTasks, numSubtaks, numCores, outfilebasename, scenefile, width, height, presetFile ):
    cmd = '{} -outputName:{}\\chunk{}.exr -strip:{},0,{} {} -rfw:0 -width={} -height={} -rps:"{}"'.format(cmdFile, outfilebasename, startTask, totalTasks, startTask, scenefile, width, height, presetFile )
    print cmd
    return cmd

def __readFromEnvironment( defaultCmdFile ):
    GOLEM_ENV = 'GOLEM'
    path = os.environ.get( GOLEM_ENV )
    if not path:
        print "No Golem environment variable found... Assuming that exec is in working folder"
        return defaultCmdFile

    sys.path.append( path )

    from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment
    env = ThreeDSMaxEnvironment()
    cmdFile = env.get3dsmaxcmdPath()
    if cmdFile:
        return cmdFile
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        return defaultCmdFile


############################f =
def run3dsMaxTask( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneSrc, sceneFile, width, height, preset, cmdFile):
    print 'run3dsMaxTask'
    outputFiles = tmpPath

    files = glob.glob( outputFiles + "*.exr" )

    for f in files:
        os.remove(f)

    if preset:
        presetFile = preset
    else:
        presetFile = os.path.join( dsmaxpath,  'renderpresets\mental.ray.daylighting.high.rps')


    cmdFile = __readFromEnvironment( cmdFile )
    if os.path.exists( sceneFile ):
        cmd = format3dsMaxCmd( cmdFile, startTask, endTask, totalTasks, numSubtasks, numCores, outputFiles, sceneFile, width, height, presetFile )
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


output = run3dsMaxTask ( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneFileSrc, sceneFile, width, height, presetFile, cmdFile )
