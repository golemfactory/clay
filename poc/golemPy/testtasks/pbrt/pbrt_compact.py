import os
import glob
import cPickle as pickle
import zlib

############################
def format_pbrt_cmd( renderer, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, scenefile ):
    return "{} --starttask {} --endtask {} --outresultbasename {} --totaltasks {} --ncores {} --subtasks {} {}".format( renderer, startTask, endTask, outfilebasename, totalTasks, numCores, numSubtasks, scenefile )

############################
def run_pbrt_task( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneFile ):
    pbrt = os.path.join( resourcePath, "pbrt.exe" )

    outputFiles = os.path.join( tmpPath, outfilebasename )

    files = glob.glob( outputFiles + "*.exr" )

    for f in files:
        os.remove(f)

    cmd = format_pbrt_cmd( pbrt, startTask, endTask, totalTasks, numSubtasks, numCores, outputFiles, os.path.join( resourcePath, sceneFile ) )
    
    print cmd
   
    os.system( cmd )

    print outputFiles

    files = glob.glob( outputFiles + "*.exr" )

    print files

    res = []

    for f in files:
        fh = open( f, "rb" )
        fileData = fh.read()
        fileData = zlib.compress( fileData )
        res.append( pickle.dumps( ( os.path.basename( f ), fileData ) ) )
        fh.close()

    return res


output = run_pbrt_task( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneFile )
        