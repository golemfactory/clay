import tempfile
import os
import sys
import glob
import cPickle as pickle
import zlib
import subprocess
import shutil
import psutil



def return_data(files):
    res = []
    for f in files:
        with open(f, "rb") as fh:
            file_data = fh.read()
        file_data = zlib.compress(file_data, 9)
        res.append(pickle.dumps((os.path.basename(f), file_data)))

    return {'data': res, 'result_type': 0}


def return_files(files):
    copy_path = os.path.normpath(os.path.join(tmp_path, ".."))
    for f in files:
        shutil.copy2(f, copy_path)

    files = [os.path.normpath(os.path.join(copy_path, os.path.basename(f))) for f in files]
    return {'data': files, 'result_type': 1}


def get_files():
    output_files = tmp_path
    return glob.glob(output_files + "/*.exr") + glob.glob(output_files + "/*.log")


def remove_old_files():
    for f in get_files():
        os.remove(f)


def __read_from_environment():
    default_cmd_file = 'blender'

    try:
        from gnr.renderingenvironment import BlenderEnvironment
    except ImportError:
        print "No Golem app found... Setting default command file"
        return default_cmd_file

    env = BlenderEnvironment()
    cmd_file = env.get_blender()
    if cmd_file:
        return cmd_file
    else:
        print "Environment not supported... Setting default command file"
        return default_cmd_file


def is_windows():
    return sys.platform == 'win32'


def exec_cmd(cmd, cur_dir, files):
    pc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = pc.communicate()
    if is_windows():
        import win32process
        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)
    pc.wait()
    with open(os.path.join(cur_dir, files + ".err.log"), 'w') as stderr:
        stderr.write(err)
    with open(os.path.join(cur_dir, files + ".log"), "w") as stdout:
        stdout.write(out)



def format_blender_render_cmd(cmd_file, output_files, outfilebasename, scene_file, script_file, start_task, engine,
                              frame):
    cmd = ["{}".format(cmd_file), "-b", "{}".format(scene_file), "-P", "{}".format(script_file),
           "-o", "{}\{}{}".format(output_files, outfilebasename, start_task), "-E", "{}".format(engine), "-F", "EXR",
           "-f", "{}".format(frame)]
    return cmd


def run_blender_task(outfilebasename, scene_file, script_src, start_task, engine, frames):

    output_files = tmp_path
    remove_old_files()

    scene_dir = os.path.dirname(scene_file)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=scene_dir, delete=False) as script_file:
        script_file.write(script_src)

    cmd_file = __read_from_environment()
    scene_file = os.path.normpath(os.path.join(os.getcwd(), scene_file))
    if not os.path.exists(os.path.normpath(scene_file)):
        print "Scene file does not exist"
        return {'data': [], 'result_type': 0}

    for frame in frames:
        cmd = format_blender_render_cmd(cmd_file, output_files, outfilebasename, scene_file, script_file.name,
                                        start_task, engine, frame)
        print cmd
        exec_cmd(cmd, output_files, outfilebasename + str(start_task) + "_" + str(frame))

    os.remove(script_file.name)

    return return_files(get_files())


output = run_blender_task(outfilebasename, scene_file, script_src, start_task, engine, frames)
