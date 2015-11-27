import cPickle as pickle
import glob
import os
import subprocess
import tempfile
import win32process
import zlib


def format_pbrt_cmd(renderer, start_task, end_task, total_tasks, num_subtasks, num_cores, outfilebasename, scenefile):
    return "{} --starttask {} --endtask {} --outresultbasename {} --totaltasks {} --ncores {} --subtasks {} {}".format(
        renderer, start_task, end_task, outfilebasename, total_tasks, num_cores, num_subtasks, scenefile)


def run_pbrt_task(path_root, start_task, end_task, total_tasks, num_subtasks, num_cores, outfilebasename, scene_src):
    pbrt = os.path.join(resourcePath, "pbrt.exe")

    output_files = os.path.join(tmp_path, outfilebasename)

    files = glob.glob(output_files + "*.exr")

    for f in files:
        os.remove(f)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pbrt", dir=os.path.join(resourcePath, "resources"),
                                                 delete=False) as tmp_scene_file:
        tmp_scene_file.write(scene_src)

        print tmp_scene_file.name

        cmd = format_pbrt_cmd(pbrt, start_task, end_task, total_tasks, num_subtasks, num_cores, output_files,
                                  tmp_scene_file.name)


        pc = subprocess.Popen(cmd)

        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)

        pc.wait()

        files = glob.glob(output_files + "*.exr")

        res = []

    if os.path.exists(tmp_scene_file.name):
        os.remove(tmp_scene_file.name)

    for f in files:
        fh = open(f, "rb")
        file_data = fh.read()
        file_data = zlib.compress(file_data, 9)
        res.append(pickle.dumps((os.path.basename(f), file_data)))
        fh.close()

    return res


output = run_pbrt_task(path_root, start_task, end_task, total_tasks, num_subtasks, num_cores, outfilebasename,
                       scene_file_src)
