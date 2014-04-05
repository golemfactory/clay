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

if __name__ == "__main__":

    totalTasks = 16
    numSubtasks = 32
    numCores = 3
    outfilebasename = "output/test_chunk_"
    sceneFile = "test_run/resources/scene.pbrt"
 
    for i in range( totalTasks ):
        run_pbrt_task( "test_run", i, i + 1, totalTasks, numSubtasks, numCores, outfilebasename, sceneFile )
