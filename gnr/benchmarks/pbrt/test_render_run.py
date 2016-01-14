import os

############################
def format_pbrt_cmd(renderer, start_task, end_task, total_tasks, num_subtasks, num_cores, outfilebasename, scenefile):
    return "{} --starttask {} --endtask {} --outresultbasename {} --totaltasks {} --ncores {} --subtasks {} {}".format(renderer, start_task, end_task, outfilebasename, total_tasks, num_cores, num_subtasks, scenefile)

############################
def run_pbrt_task(path_root, start_task, end_task, total_tasks, num_subtasks, num_cores, outfilebasename, scene_file):
    pbrt = os.path.join(path_root, "pbrt.exe")

    cmd = format_pbrt_cmd(pbrt, start_task, end_task, total_tasks, num_subtasks, num_cores, outfilebasename, scene_file)
    
    print cmd
   
    os.system(cmd)

if __name__ == "__main__":

    total_tasks = 16
    num_subtasks = 32
    num_cores = 3
    outfilebasename = "output/test_chunk_"
    scene_file = "test_run/resources/scene.pbrt"
 
    for i in range(total_tasks):
        run_pbrt_task("test_run", i, i + 1, total_tasks, num_subtasks, num_cores, outfilebasename,
                      scene_file)
