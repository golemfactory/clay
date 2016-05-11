import os
import sys
import glob
import cPickle as pickle
import zlib
import zipfile
import subprocess
import psutil
import math
import shutil


def format_test_vray_cmd(cmd_file, output_file, outfilebasename, scenefile, width, height, rt_engine, num_threads):
    cmd = ["{}".format(cmd_file), "-imgFile={}/{}.exr".format(output_file, outfilebasename),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width), "-imgHeight={}".format(height),
           "-region={};{};{};{}".format(start_box[0], start_box[1], start_box[0] + box[0], start_box[1] + box[1]),
           "-autoClose=1", "-display=0", "-rt_engine={}".format(rt_engine), "-numThreads={}".format(num_threads) ]
    return cmd


def format_test_vray_cmd_with_parts(cmd_file, frames,  output_file, outfilebasename, scenefile, width, height, rt_engine, num_threads):
    cmd = ["{}".format(cmd_file), "-imgFile={}/{}.exr".format(output_file, outfilebasename),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width), "-imgHeight={}".format(height),
           "-frames={}".format(frames), "-region={};{};{};{}".format(0, start_box[1], width),
           "-autoClose=1", "-display=0", "-rtEngine={}".format(rt_engine), "-numThreads={}".format(num_threads)]
    return cmd


def format_vray_cmd(cmd_file, start_task, start_part, h_tasks, total_tasks, output_file, outfilebasename, scenefile,
                    width, height, rt_engine, num_threads):
    if 'generateStartBox' in globals():
        return format_test_vray_cmd(cmd_file, output_file, outfilebasename, scenefile, width, height, rt_engine, num_threads)
    w_tasks = total_tasks / h_tasks
    part_width = width / w_tasks
    part_height = height / h_tasks
    left = ((int(start_part) - 1) / int(h_tasks)) * part_width
    right = left + part_width
    upper = ((start_part - 1) % h_tasks) * part_height
    lower = upper + part_height
    cmd = ["{}".format(cmd_file), "-imgFile={}/{}{}.exr".format(output_file, outfilebasename, start_task),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width),  "-imgHeight={}".format(height),
           "-region={};{};{};{}".format(left, upper, right, lower), "-autoClose=1", "-display=0",
           "-rtEngine={}".format(rt_engine), "-numThreads={}".format(num_threads)]
    return cmd


def format_vray_cmd_with_frames(cmd_file, frames, output_file, outfilebasename, scenefile, width, height, rt_engine, num_threads):
    cmd = ["{}".format(cmd_file), "-imgFile={}/{}.exr".format(output_file, outfilebasename),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width), "-imgHeight={}".format(height),
           "-frames={}".format(frames), "-region={};{};{};{}".format(0, 0, width, height),
           "-autoClose=1", "-display=0", "-rtEngine={}".format(rt_engine), "-numThreads={}".format(num_threads) ]
    return cmd


def format_vray_cmd_with_parts(cmd_file, frames, parts, start_part, output_file, outfilebasename, scenefile, width, height, rt_engine, num_threads):
    if 'generateStartBox' in globals():
        return format_test_vray_cmd_with_parts(cmd_file, frames, output_file, outfilebasename, scenefile, width, height, rt_engine, num_threads)
    part = ((start_part - 1) % parts) + 1
    upper = int(math.floor((part - 1) * (float(height) / float(parts))))
    lower = int(math.floor(part * (float(height) / float(parts))))
    cmd = ["{}".format(cmd_file), "-imgFile={}/{}.{}.exr".format(output_file, outfilebasename, part),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width), "-imgHeight={}".format(height),
           "-frames={}".format(frames), "-region={};{};{};{}".format(0, upper, width, lower),
           "-autoClose=1", "-display=0", "-rtEngine={}".format(rt_engine),  "-numThreads={}".format(num_threads)]
    return cmd

def __read_from_environment():
    default_cmd = "vray"
    default_win_cmd = "vray.exe"
    try:
        from gnr.renderingenvironment import VRayEnvironment
    except ImportError:
        print "No Golem app found... Setting default command file"
        if is_windows():
            return default_win_cmd
        else:
            return default_cmd

    env = VRayEnvironment()
    cmd_file = env.get_cmd_path()
    if cmd_file:
        return cmd_file
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        if is_windows():
            return default_win_cmd
        else:
            return default_cmd

def output_number(num):
    num = str(num)
    return num.zfill(4)


############################
def return_data(files):
    res = []
    for f in files:
        with open(f, "rb") as fh:
            file_data = fh.read()
        file_data = zlib.compress(file_data, 9)
        res.append(pickle.dumps((os.path.basename(f), file_data)))

    return { 'data': res, 'result_type': 0 }

############################
def is_windows():
    return sys.platform == 'win32'

def exec_cmd(cmd, nice=20):
    pc = subprocess.Popen(cmd)
    if is_windows():
        import win32process
        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)
    else:
        p = psutil.Process(pc.pid)
        p.nice(nice)

    pc.wait()

############################
def return_files(files):
    copy_path = os.path.normpath(os.path.join(tmp_path, ".."))
    for f in files:
        shutil.copy2(f, copy_path)

    files = [ os.path.normpath(os.path.join(copy_path, os.path.basename(f))) for f in files]
    return {'data': files, 'result_type': 1 }

############################
def run_vray_task(path_root, start_task, start_part, end_task, h_task, total_tasks, outfilebasename, scene_file, width,
                  height, rt_engine, use_frames, frames, parts, num_threads):
    print frames

    output_files = tmp_path

    files = glob.glob(output_files + "/*.exr")

    for f in files:
        os.remove(f)

    print "scene_file " + scene_file
    if os.path.splitext(scene_file)[1] == '.zip':
        with zipfile.ZipFile(scene_file , "r", allowZip64 = True) as z:
            z.extractall(os.getcwd())
        scene_file = glob.glob("*.vrscene")[0]


    cmd_file = __read_from_environment()
    print "cmd_file " + cmd_file
    if os.path.exists(scene_file):
        if use_frames:
            frames = parse_frames (frames)
            if parts == 1:
                if len(frames) == 1:
                    outfilebasename = "{}.{}".format(outfilebasename, output_number(frames[0]))
                cmd = format_vray_cmd_with_frames(cmd_file, frames, output_files, outfilebasename, scene_file, width, height, rt_engine, num_threads)
            else:
                outfilebasename = "{}.{}".format(outfilebasename, output_number(frames[0]))
                cmd = format_vray_cmd_with_parts(cmd_file, frames, parts, start_part, output_files, outfilebasename,
                                                 scene_file, width, height, rt_engine, num_threads)
        else:
            cmd = format_vray_cmd(cmd_file, start_task, start_part, h_task, total_tasks, output_files,outfilebasename,
                                  scene_file, width, height, rt_engine, num_threads)
    else:
        print "Scene file does not exist"
        return {'data': [], 'result_type': 0 }

    print cmd

    exec_cmd(cmd)

    files = glob.glob(output_files + "/*.exr")

    return return_data(files)

def parse_frames(frames):
    return ";".join([ u"{}".format(frame) for frame in frames ])

output = run_vray_task(path_root, start_task, start_part, end_task, h_task, total_tasks, outfilebasename, scene_file,
                       width, height, rt_engine, use_frames, frames, parts, num_threads)
