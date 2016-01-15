import tempfile
import os
import sys
import glob
import cPickle as pickle
import zlib
import subprocess
import psutil
import shutil


def format_lux_renderer_cmd(cmd_file, start_task, output_file, outfilebasename, scenefile, num_threads):
    cmd = ["{}".format(cmd_file), "{}".format(scenefile), "-o",
           "{}/{}{}.png".format(output_file, outfilebasename, start_task), "-t", "{}".format(num_threads)]
    print cmd
    return cmd


def __read_from_environment():
    win_default_cmd = "luxconsole.exe"
    default_cmd = "luxconsole"
    try:
        from gnr.renderingenvironment import LuxRenderEnvironment
    except ImportError:
        print "No Golem app found... Setting default command file"
        if is_windows():
            return win_default_cmd
        else:
            return default_cmd

    env = LuxRenderEnvironment()
    cmd_file = env.get_lux_console()
    if cmd_file:
        return cmd_file
    else:
        print "Environment not supported... Setting default command file"
        if is_windows():
            return win_default_cmd
        else:
            return default_cmd


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


def is_windows():
    return sys.platform == 'win32'


def exec_cmd(cmd, nice=20, cur_dir, files):
    pc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if is_windows():
        import win32process
        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)
    else:
        p = psutil.Process(pc.pid)
        p.nice(nice)
    stdout = open(os.path.join(cur_dir, files, "out.log"), 'w')
    stdout.write(out)
    stdout.close()
    stderr = open(os.path.join(cur_dir, files, "err.log"), 'w')
    stderr.write(err)
    stderr.close()
    pc.wait()
    


def run_lux_renderer_task(start_task, outfilebasename, scene_file_src, scene_dir, num_cores, own_binaries, lux_console):
    print 'LuxRenderer Task'

    output_files = tmp_path

    files = glob.glob(output_files + "/*.png") + glob.glob(output_files + "/*.flm") + glob.glob(output_files + "/*.log")

    for f in files:
        os.remove(f)

    scene_dir = os.path.normpath(os.path.join(os.getcwd(), scene_dir))

    if own_binaries:
        cmd_file = lux_console
    else:
        cmd_file = __read_from_environment()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".lxs", dir=scene_dir, delete=False) as tmp_scene_file:
        tmp_scene_file.write(scene_file_src)

    cmd = format_lux_renderer_cmd(cmd_file, start_task, output_files, outfilebasename, tmp_scene_file.name,
                                  num_threads)


    prev_dir = os.getcwd()
    os.chdir(scene_dir)

    exec_cmd(cmd, cur_dir=prev_dir, files=output_files)

    os.chdir(prev_dir)
    files = glob.glob(output_files + "/*.png") + glob.glob(output_files + "/*.flm") + glob.glob(output_files + "/*.log")

    os.remove(tmp_scene_file.name)

    return return_files(files)


output = run_lux_renderer_task(start_task, outfilebasename, scene_file_src, scene_dir, num_threads, own_binaries,
                               lux_console)
