import os
import glob
import cPickle as pickle
import zlib
import subprocess
import platform, psutil
import win32api, win32process
import tempfile

############################
def format_pbrt_cmd(renderer, start_task, end_task, total_tasks, num_subtasks, num_cores, outfilebasename, scenefile):
    return "{} --starttask {} --endtask {} --outresultbasename {} --totaltasks {} --ncores {} --subtasks {} {}".format(renderer, start_task, end_task, outfilebasename, total_tasks, num_cores, num_subtasks, scenefile)

############################
def run_pbrt_task(path_root, start_task, end_task, total_tasks, num_subtasks, num_cores, outfilebasename, sceneSrc):
    pbrt = os.path.join(resourcePath, "pbrt.exe")

    output_files = os.path.join(tmp_path, outfilebasename)

    files = glob.glob(output_files + "*.exr")

    for f in files:
        os.remove(f)

    tmpSceneFile = tempfile.TemporaryFile(suffix = ".pbrt", dir = os.path.join(resourcePath, "resources"))
    tmpSceneFile.close()
    print sceneSrc
    f = open(tmpSceneFile.name, 'w')
    f.write(sceneSrc)
    f.close()
    
    print tmpSceneFile.name

    if os.path.exists(tmpSceneFile.name):
        cmd = format_pbrt_cmd(pbrt, start_task, end_task, total_tasks, num_subtasks, num_cores, output_files, tmpSceneFile.name)
    else:
        print "Scene file does not exist"
        
    print cmd
   
    pc = subprocess.Popen(cmd)

    win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)

    pc.wait()

    print output_files

    files = glob.glob(output_files + "*.exr")

    print files

    res = []

    for f in files:
        fh = open(f, "rb")
        file_data = fh.read()
        file_data = zlib.compress(file_data, 9)
        res.append(pickle.dumps((os.path.basename(f), file_data)))
        fh.close()

    #os.remove(tmpSceneFile.name)

    return res


output = run_pbrt_task(path_root, start_task, end_task, total_tasks, num_subtasks, num_cores, outfilebasename, scene_fileSrc)
        