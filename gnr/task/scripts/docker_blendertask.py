import os
import sys
import subprocess
import psutil


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


def exec_cmd(cmd, nice=20):
    pc = subprocess.Popen(cmd)
    if is_windows():
        import win32process
        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)
    else:
        p = psutil.Process(pc.pid)
        if psutil.__version__ == '1.2.1':
            p.set_nice(nice)  # imapp/blender has psutil ver. 1.2.1
        else:
            p.nice(nice)

    pc.wait()


def format_blender_render_cmd(cmd_file, output_dir, outfilebasename, scene_file, script_file, start_task, engine,
                              frame):
    cmd = ["{}".format(cmd_file), "-b", "{}".format(scene_file), "-P", "{}".format(script_file),
           "-o", "{}/{}{}".format(output_dir, outfilebasename, start_task), "-E", "{}".format(engine), "-F", "EXR",
           "-f", "{}".format(frame)]
    return cmd


def run_blender_task(outfilebasename, scene_file, script_src, start_task, engine, frames):

    cmd_file = __read_from_environment()
    scene_file = os.path.normpath(scene_file)
    if not os.path.exists(scene_file):
        print "Scene file {} does not exist".format(scene_file)
        return {'data': [], 'result_type': 0}

    with open("/golem/output/blenderscript.py", "w") as script_file:
        script_file.write(script_src)

    for frame in frames:
        cmd = format_blender_render_cmd(
            cmd_file, output_dir, outfilebasename, scene_file, script_file.name,
            start_task, engine, frame)
        print cmd
        exec_cmd(cmd)

    os.remove(script_file.name)


output_dir = "/golem/output/"
output = run_blender_task(outfilebasename, scene_file, script_src, start_task, engine, frames)

