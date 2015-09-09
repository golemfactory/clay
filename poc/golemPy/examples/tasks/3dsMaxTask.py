import os
import sys
import glob
import cPickle as pickle
import zlib
import zipfile
import subprocess
import win32process
import shutil

def format_3ds_max_cmd(cmd_file, start_task, end_task, total_tasks, output_file, outfilebasename, scenefile, width, height, preset_file, overlap):
    cmd = '{} -outputName:{}\\{}.exr -strip:{},{},{} "{}" -frames:0 -stillFrame -rfw:0 -width={} -height={} -rps:"{}"'.format(cmd_file,output_file,  outfilebasename, total_tasks, overlap, start_task, scenefile, width, height, preset_file)
    return cmd

def format_3ds_max_cmd_with_frames(cmd_file, frames, output_file, outfilebasename, scenefile, width, height, preset_file):
    cmd = '{} -outputName:{}\\{}.exr -frames:{} "{}" -rfw:0 -width={} -height={} -rps:"{}"'.format(cmd_file, output_file, outfilebasename, frames, scenefile, width, height, preset_file)
    return cmd

def format_3ds_max_cmd_with_parts(cmd_file, frames, parts, start_task, output_file, outfilebasename, scene_file, width, height, preset_file, overlap):
    part = ((start_task - 1) % parts) + 1
    cmd = '{} -outputName:{}\\{}.exr -frames:{} -strip:{},{},{} "{}" -rfw:0 -width={} -height={} -rps:"{}"'.format(cmd_file, output_file, outfilebasename, frames, parts, overlap, part, scene_file, width, height, preset_file)
    return cmd

GOLEM_ENV = 'GOLEM'

def __read_from_environment(default_cmd_file, num_cores):

    path = os.environ.get(GOLEM_ENV)
    if not path:
        print "No Golem environment variable found... Assuming that exec is in working folder"
        return default_cmd_file

    sys.path.append(path)

    from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment
    env = ThreeDSMaxEnvironment()
    cmd_file = env.get_3ds_max_cmd_path()
    if cmd_file:
    #    env.set_n_threads(num_cores)
        return cmd_file
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        return default_cmd_file

###########################
def return_data(files):
    res = []
    for f in files:
        with open(f, "rb") as fh:
            file_data = fh.read()
        file_data = zlib.compress(file_data, 9)
        res.append(pickle.dumps((os.path.basename(f), file_data)))

    return { 'data': res, 'result_type': 0 }

############################
def return_files(files):
    copy_path = os.path.normpath(os.path.join(tmp_path, ".."))
    for f in files:
        shutil.copy2(f, copy_path)

    files = [ os.path.normpath(os.path.join(copy_path, os.path.basename(f))) for f in files]
    return {'data': files, 'result_type': 1 }



############################f =
def run_3ds_max_task(path_root, start_task, end_task, total_tasks, outfilebasename, scene_file, width, height, preset, cmd_file, use_frames, frames, parts, num_cores, overlap):
    print 'run_3ds_max_task'
    output_files = tmp_path

    files = glob.glob(output_files + "*.exr")

    for f in files:
        os.remove(f)

    if os.path.splitext(scene_file)[1] == '.zip':
        with zipfile.ZipFile(scene_file , "r", allowZip64 = True) as z:
            z.extractall(os.getcwd())
        scene_file = glob.glob("*.max")[0]

    if preset:
        preset_file = os.path.normpath( os.path.join(os.getcwd(), preset))
    else:
        preset_file = os.path.join(dsmaxpath,  'renderpresets\mental.ray.daylighting.high.rps')


    cmd_file = __read_from_environment(cmd_file, num_cores)
    if os.path.exists(scene_file):
        if use_frames:
            frames = parse_frames(frames)
            if parts == 1:
                cmd = format_3ds_max_cmd_with_frames(cmd_file, frames, output_files, outfilebasename, scene_file, width, height, preset_file)
            else:
                cmd = format_3ds_max_cmd_with_parts(cmd_file, frames, parts, start_task, output_files, outfilebasename, scene_file, width, height, preset_file, overlap)
        else:
            cmd = format_3ds_max_cmd(cmd_file, start_task, end_task, total_tasks, output_files, outfilebasename, scene_file, width, height, preset_file, overlap)

    else:
        print "Scene file does not exist"
        return {'data': [], 'result_type': 0 }

    print cmd

    pc = subprocess.Popen(cmd)

    win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)


    pc.wait()

    files = glob.glob(output_files + "\*.exr")

    return return_data(files)

def parse_frames(frames):
    return ",".join([ u"{}".format(frame) for frame in frames ])

output = run_3ds_max_task (path_root, start_task, end_task, total_tasks, outfilebasename, scene_file, width, height, preset_file, cmd_file, use_frames, frames, parts, num_cores, overlap)
