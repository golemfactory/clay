from __future__ import print_function

import os
import subprocess
import sys
from multiprocessing import cpu_count

# pylint: disable=import-error
import params  # This module is generated before this script is run

BLENDER_COMMAND = "blender"


def exec_cmd(cmd):
    pc = subprocess.Popen(cmd)
    return pc.wait()


# pylint: disable=too-many-arguments
def format_blender_render_cmd(outfilebasename, scene_file, script_file,
                              start_task, frame, output_format):
    cmd = [
        "{}".format(BLENDER_COMMAND),
        "-b", "{}".format(scene_file),
        "-y",  # enable scripting by default
        "-P", "{}".format(script_file),
        "-o", "{}/{}_{}".format(params.OUTPUT_DIR,
                                outfilebasename,
                                start_task),
        "-noaudio",
        "-F", "{}".format(output_format.upper()),
        "-t", "{}".format(cpu_count()),
        "-f", "{}".format(frame)
    ]
    return cmd


# pylint: disable=too-many-arguments
def run_blender_task(outfilebasename, scene_file, script_src, start_task,
                     frames, output_format):
    scene_file = os.path.normpath(scene_file)
    if not os.path.exists(scene_file):
        print("Scene file '{}' does not exist".format(scene_file),
              file=sys.stderr)
        sys.exit(1)

    blender_script_path = "{}/blenderscript.py".format(params.WORK_DIR)
    with open(blender_script_path, "w") as script_file:
        script_file.write(script_src)

    for frame in frames:
        cmd = format_blender_render_cmd(outfilebasename, scene_file,
                                        script_file.name, start_task,
                                        frame, output_format)
        print(cmd, file=sys.stderr)
        exit_code = exec_cmd(cmd)
        if exit_code is not 0:
            sys.exit(exit_code)


run_blender_task(params.outfilebasename, params.scene_file, params.script_src,
                 params.start_task, params.frames, params.output_format)
