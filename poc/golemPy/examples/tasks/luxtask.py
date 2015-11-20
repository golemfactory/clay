import tempfile
import os
import sys
import glob
import cPickle as pickle
import zlib
import zipfile
import subprocess
import psutil
import shutil


def format_lux_renderer_cmd(cmd_file, start_task, output_file, outfilebasename, scenefile, num_threads):
    cmd = ["{}".format(cmd_file), "{}".format(scenefile), "-o",
           "{}/{}{}.png".format(output_file, outfilebasename, start_task), "-t", "{}".format(num_threads)]
    print cmd
    return cmd


GOLEM_ENV = 'GOLEM'


def __read_from_environment():
    path = os.environ.get(GOLEM_ENV)
    if not path:
        print "No Golem environment variable found... Assuming that exec is in working folder"
        if is_windows():
            return 'luxconsole.exe'
        else:
            return 'luxconsole'

    sys.path.append(path)

    from examples.gnr.RenderingEnvironment import LuxRenderEnvironment
    env = LuxRenderEnvironment()
    cmd_file = env.get_lux_console()
    if cmd_file:
        return cmd_file
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        if is_windows():
            return 'luxconsole.exe'
        else:
            return 'luxconsole'


############################
def return_data(files):
    res = []
    for f in files:
        with open(f, "rb") as fh:
            file_data = fh.read()
        file_data = zlib.compress(file_data, 9)
        res.append(pickle.dumps((os.path.basename(f), file_data)))

    return {'data': res, 'result_type': 0}


############################
def return_files(files):
    copy_path = os.path.normpath(os.path.join(tmp_path, ".."))
    for f in files:
        shutil.copy2(f, copy_path)

    files = [os.path.normpath(os.path.join(copy_path, os.path.basename(f))) for f in files]
    return {'data': files, 'result_type': 1}


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


def make_tmp_file(scene_dir, scene_src):
    if is_windows():
        tmp_scene_file = tempfile.TemporaryFile(suffix=".lxs", dir=scene_dir)
        tmp_scene_file.close()
        f = open(tmp_scene_file.name, 'w')
        f.write(scene_src)
        f.close()

        return tmp_scene_file.name
    else:
        tmp_scene_file = os.path.join(scene_dir, "tmp_scene_file.lxs")
        f = open(tmp_scene_file, "w")
        f.write(scene_src)
        f.close()
        return tmp_scene_file


############################
def run_lux_renderer_task(start_task, outfilebasename, scene_file_src, scene_dir, num_cores, own_binaries, lux_console):
    print 'LuxRenderer Task'

    output_files = tmp_path

    files = glob.glob(output_files + "/*.png") + glob.glob(output_files + "/*.flm")

    for f in files:
        os.remove(f)

    scene_dir = os.path.normpath(os.path.join(os.getcwd(), scene_dir))
    tmp_scene_file = make_tmp_file(scene_dir, scene_file_src)

    if own_binaries:
        cmd_file = lux_console
    else:
        cmd_file = __read_from_environment()
    if os.path.exists(tmp_scene_file):
        print tmp_scene_file
        cmd = format_lux_renderer_cmd(cmd_file, start_task, output_files, outfilebasename, tmp_scene_file, num_threads)
    else:
        print "Scene file does not exist"
        return {'data': [], 'result_type': 0}

    prev_dir = os.getcwd()
    os.chdir(scene_dir)

    exec_cmd(cmd)

    os.chdir(prev_dir)
    files = glob.glob(output_files + "/*.png") + glob.glob(output_files + "/*.flm")

    return return_files(files)


output = run_lux_renderer_task(start_task, outfilebasename, scene_file_src, scene_dir, num_threads, own_binaries,
                               lux_console)
