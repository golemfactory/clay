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
    return glob.glob(output_files + "/*.exr")


def remove_old_files():
    for f in get_files():
        os.remove(f)


GOLEM_ENV = 'GOLEM'


def __read_from_environment():
    default_cmd_file = 'blender'

    path = os.environ.get(GOLEM_ENV)
    if not path:
        print "No Golem environment variable found..."
        return default_cmd_file

    sys.path.append(path)

    from examples.gnr.renderingenvironment import BlenderEnvironment
    env = BlenderEnvironment()
    cmd_file = env.get_blender()
    if cmd_file:
        return cmd_file
    else:
        return default_cmd_file


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


def format_blender_render_cmd(cmd_file, output_files, outfilebasename, scene_file, script_file, start_task, engine,
                              frame):
    cmd = ["{}".format(cmd_file), "-b", "{}".format(scene_file), "-P", "{}".format(script_file),
           "-o", "{}\{}{}".format(output_files, outfilebasename, start_task), "-E", "{}".format(engine), "-F", "EXR",
           "-f", "{}".format(frame)]
    return cmd


def run_blender_task(outfilebasename, scene_file, script_src, start_task, engine, frames):
    print "Blender Render Task"

    output_files = tmp_path

    remove_old_files()

    scene_dir = os.path.dirname(scene_file)
    script_file = tempfile.TemporaryFile(suffix=".py", dir=scene_dir)
    script_file.close()
    with open(script_file.name, 'w') as f:
        f.write(script_src)

    cmd_file = __read_from_environment()
    scene_file = os.path.normpath(os.path.join(os.getcwd(), scene_file))
    if not os.path.exists(os.path.normpath(scene_file)):
        print "Scene file does not exist"
        return {'data': [], 'result_type': 0}

    for frame in frames:
        cmd = format_blender_render_cmd(cmd_file, output_files, outfilebasename, scene_file, script_file.name,
                                        start_task, engine, frame)
        print cmd
        exec_cmd(cmd)

    return return_files(get_files())


output = run_blender_task(outfilebasename, scene_file, script_src, start_task, engine, frames)
