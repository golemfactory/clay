import os
import glob
import cPickle as pickle
import zlib
import subprocess
import platform, psutil
import win32api, win32process
import tempfile

############################
def format_pbrt_cmd( renderer, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, scenefile ):
    return "{} --starttask {} --endtask {} --outresultbasename {} --totaltasks {} --ncores {} --subtasks {} {}".format( renderer, startTask, endTask, outfilebasename, totalTasks, numCores, numSubtasks, scenefile )

############################f = 
def run_pbrt_task( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneSrc ):
    pbrt = os.path.join( resourcePath, "pbrt.exe" )

    outputFiles = os.path.join( tmpPath, outfilebasename )

    files = glob.glob( outputFiles + "*.exr" )

    for f in files:
        os.remove(f)

    tmpSceneFile = tempfile.TemporaryFile( suffix = ".pbrt", dir = resourcePath )
    tmpSceneFile.close()
    print sceneSrc
    f = open(tmpSceneFile.name, 'w')
    f.write( sceneSrc )
    f.close()
    
    print tmpSceneFile.name

    if os.path.exists( tmpSceneFile.name ):
        cmd = format_pbrt_cmd( pbrt, startTask, endTask, totalTasks, numSubtasks, numCores, outputFiles, tmpSceneFile.name )
    else:
        print "Scene file does not exist"
        return []
        
    print cmd
   
    pc = subprocess.Popen( cmd )

    win32process.SetPriorityClass( pc._handle, win32process.IDLE_PRIORITY_CLASS )

    pc.wait()

    print outputFiles

    files = glob.glob( outputFiles + "*.exr" )


    res = []

    for f in files:
        fh = open( f, "rb" )
        fileData = fh.read()
        fileData = zlib.compress( fileData, 9 )
        res.append( pickle.dumps( ( os.path.basename( f ), fileData ) ) )
        fh.close()


    return { 'data': res, 'resultType': 0 }


output = run_pbrt_task( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneFileSrc )
        