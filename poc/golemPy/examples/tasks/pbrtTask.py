import os
import glob
import cPickle as pickle
import zlib
import subprocess
import platform, psutil
import tempfile
import shutil
import sys

############################
def format_pbrt_cmd( renderer, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, scenefile ):
    return ["{}".format(renderer), "--starttask", "{}".format( startTask ), "--endtask", "{}".format( endTask ),
            "--outresultbasename", "{}".format( outfilebasename ),  "--totaltasks",  "{}".format( totalTasks ),
            "--ncores", "{}".format( numCores), "--subtasks", "{}".format( numSubtasks ), "{}".format( scenefile )]

############################
def returnData( files ):
    res = []
    for f in files:
        fh = open( f, "rb" )
        fileData = fh.read()
        fileData = zlib.compress( fileData, 9 )
        res.append( pickle.dumps( ( os.path.basename( f ), fileData ) ) )
        fh.close()

    return { 'data': res, 'resultType': 0 }

############################
def returnFiles( files ):
    copyPath = os.path.normpath( os.path.join( tmpPath, "..") )
    for f in files:
        shutil.copy2( f, copyPath )

    files = [ os.path.normpath( os.path.join( copyPath, os.path.basename( f ) ) ) for f in files]
    return {'data': files, 'resultType': 1 }

############################
def isWindows():
    return sys.platform == 'win32'

def execCmd( cmd, nice = 20 ):
    pc = subprocess.Popen( cmd )
    if isWindows():
        import win32process
        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS )
    else:
        p = psutil.Process(pc.pid)
        p.set_nice( nice )

    pc.wait()

def makeTmpFile( sceneDir, sceneSrc ):
    if isWindows():
        tmpSceneFile = tempfile.TemporaryFile( suffix = ".pbrt", dir = sceneDir )
        tmpSceneFile.close()
        f = open(tmpSceneFile.name, 'w')
        f.write( sceneSrc )
        f.close()

        return tmpSceneFile.name
    else:
        tmpSceneFile = os.path.join( sceneDir, "tmpSceneFile.pbrt" )
        f = open(tmpSceneFile, "w")
        f.write( sceneSrc )
        f.close()
        return tmpSceneFile


############################f = 
def run_pbrt_task( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneSrc, sceneDir, pbrtPath ):
    pbrt = pbrtPath

    outputFiles = os.path.join( tmpPath, outfilebasename )

    files = glob.glob( outputFiles + "*.exr" )

    for f in files:
        os.remove(f)


    tmpSceneFile = makeTmpFile( sceneDir, sceneSrc )

    if os.path.exists( tmpSceneFile ):
        cmd = format_pbrt_cmd( pbrt, startTask, endTask, totalTasks, numSubtasks, numCores, outputFiles, tmpSceneFile )
    else:
        print "Scene file does not exist"
        return {'data': [], 'resultType': 0 }
        
    print cmd
    prevDir = os.getcwd()
    os.chdir( sceneDir )

    execCmd( cmd )

    os.chdir( prevDir )

    print outputFiles

    files = glob.glob( outputFiles + "*.exr" )

    return returnData( files )


output = run_pbrt_task( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneFileSrc, sceneDir, pbrtPath )
        