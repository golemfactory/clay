import os

############################
def format_pbrt_cmd( renderer, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, scenefile ):
    return "{} --starttask {} --endtask {} --outresultbasename {} --totaltasks {} --ncores {} --subtasks {} {}".format( renderer, startTask, endTask, outfilebasename, totalTasks, numCores, numSubtasks, scenefile )

############################
def run_pbrt_task( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneFile ):
    pbrt = os.path.join( pathRoot, "pbrt.exe" )

    cmd = format_pbrt_cmd( pbrt, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneFile )
    
    print cmd
   
    os.system( cmd )

run_pbrt_task( pathRoot, startTask, endTast, totalTasks, numSubtasks, numCores, outfilebasename, sceneFile )
        