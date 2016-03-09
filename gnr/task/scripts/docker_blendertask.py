from __future__ import print_function

import os
import sys
import subprocess

from params import *


BLENDER_COMMAND = "blender"
OUTPUT_DIR = "/golem/output"


def exec_cmd(cmd):
    pc = subprocess.Popen(cmd)
    return pc.wait()


def format_blender_render_cmd(cmd_file, output_dir, outfilebasename, scene_file, script_file, start_task, engine,
                              frame):
    cmd = ["{}".format(cmd_file), "-b", "{}".format(scene_file), "-P", "{}".format(script_file),
           "-o", "{}/{}{}".format(output_dir, outfilebasename, start_task), "-E", "{}".format(engine), "-F", "EXR",
           "-f", "{}".format(frame)]
    return cmd


def run_blender_task(outfilebasename, scene_file, script_src, start_task, engine, frames):

    scene_file = os.path.normpath(scene_file)
    if not os.path.exists(scene_file):
        print("Scene file '{}' does not exist".format(scene_file),
              file=sys.stderr)
        sys.exit(1)

    blender_script_path = OUTPUT_DIR + "/blenderscript.py"
    with open(blender_script_path, "w") as script_file:
        script_file.write(script_src)

    try:
        for frame in frames:
            cmd = format_blender_render_cmd(
                BLENDER_COMMAND, OUTPUT_DIR, outfilebasename, scene_file,
                script_file.name, start_task, engine, frame)
            print(cmd)
            exit_code = exec_cmd(cmd)
            if exit_code is not 0:
                sys.exit(exit_code)
    finally:
        os.remove(script_file.name)


output = run_blender_task(outfilebasename, scene_file, script_src,
                          start_task, engine, frames)

