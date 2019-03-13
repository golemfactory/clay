import os
import stat
import subprocess
import sys
from multiprocessing import cpu_count
from typing import List

from . import scenefileeditor

BLENDER_COMMAND = "blender"


def exec_cmd(cmd):
    pc = subprocess.Popen(cmd)
    return pc.wait()


# pylint: disable=too-many-arguments
def format_blender_render_cmd(outfilebasename,
                              scene_file,
                              script_file,
                              frames,
                              output_format,
                              mounted_paths,
                              num_threads=cpu_count(),
                              set_output_path=True) -> List[str]:
    cmd = [
        "{}".format(BLENDER_COMMAND),
        "-b", "{}".format(scene_file),
        "-y",  # enable scripting by default
        "-P", "{}".format(script_file)
    ]

    if set_output_path:
        cmd += ["-o", "{}/{}".format(mounted_paths["OUTPUT_DIR"],
                                     outfilebasename)]

    cmd += [
        "-noaudio",
        "-F", "{}".format(output_format.upper()),
        "-t", "{}".format(num_threads),
        "-f", "{}".format(",".join(map(str, frames)))
    ]
    return cmd


# Example parameters:
# {
#   "scene_file" : "scene.blend"
#   "resolution" : [ 1920, 1080 ],
#   "use_compositing" : False,
#   "samples" : 100,
#   "frames" : [1,2,3],
#   "output_format" : "PNG",
#   "crops" :
#   [
#       {
#           "outfilebasename" : "output_1.png",
#           "border_x" : [ 0.0, 1.0 ],
#           "border_y" : [ 0.0, 1.0 ]
#       }
#   ]
# }


def params_to_dict(params) -> dict:
    params_dict = dict()

    params_dict["scene_file"] = params.scene_file
    params_dict["frames"] = params.frames
    params_dict["output_format"] = params.output_format
    params_dict["resolution"] = params.resolution
    params_dict["use_compositing"] = params.use_compositing
    params_dict["samples"] = params.samples
    params_dict["crops"] = list()
    for crop_params in params.crops:
        crop = crop_params.copy()
        borders_y = crop["borders_y"]
        borders_y = [float(borders_y[0]),
                     float(borders_y[1])]
        crop["borders_y"] = borders_y
        params_dict["crops"].append(crop)

    return params_dict


def params_to_paths(params) -> dict:
    mounted_paths = dict()
    mounted_paths["RESOURCES_DIR"] = params.RESOURCES_DIR
    mounted_paths["WORK_DIR"] = params.WORK_DIR
    mounted_paths["OUTPUT_DIR"] = params.OUTPUT_DIR
    return mounted_paths


def gen_blender_script_file(parameters: dict,
                            crop: dict,
                            mounted_paths: dict,
                            crop_counter: int,
                            output_path=None):

    outfilebasename = crop["outfilebasename"]
    borders_x = crop["borders_x"]
    borders_y = crop["borders_y"]

    script_file = "scriptfile-" \
                  + outfilebasename \
                  + "-[crop_num=" \
                  + str(crop_counter) \
                  + "].py"

    script_file = scenefileeditor.generate_blender_crop_file(
        script_file,
        parameters["resolution"],
        borders_x,
        borders_y,
        parameters["use_compositing"],
        parameters["samples"],
        mounted_paths,
        output_path)

    return script_file


def gen_blender_command(parameters: dict,
                        crop: dict,
                        mounted_paths: dict,
                        script_file: str,
                        num_threads=cpu_count(),
                        set_output_path=True):

    outfilebasename = crop["outfilebasename"]
    frames = parameters["frames"]
    output_format = parameters["output_format"].lower()

    cmd = format_blender_render_cmd(outfilebasename, parameters["scene_file"],
                                    script_file,
                                    frames,
                                    output_format,
                                    mounted_paths,
                                    num_threads,
                                    set_output_path)

    return cmd


def render(parameters: dict,
           mounted_paths: dict) -> List[dict]:

    crops = parameters["crops"]

    crop_counter = 0
    output_info = list()

    for crop in crops:

        script_file = gen_blender_script_file(parameters,
                                              crop, mounted_paths,
                                              crop_counter)
        cmd = gen_blender_command(parameters, crop, mounted_paths, script_file)

        output_format = parameters["output_format"].lower()

        results_list = list()
        for frame in parameters["frames"]:
            filename = crop["outfilebasename"] \
                       + "{:04d}.".format(frame) \
                       + output_format
            results_list.append(filename)

        crop_info = dict()
        crop_info["crop"] = crop
        crop_info["results"] = results_list

        output_info.append(crop_info)

        print(cmd, file=sys.stderr)
        exit_code = exec_cmd(cmd)
        if exit_code is not 0:
            sys.exit(exit_code)

        crop_counter += 1

    return output_info


# pylint: disable-msg=too-many-locals
def gen_render_shell_scripts(parameters: dict,
                             mounted_paths: dict,
                             use_fixed_output_path=False) -> List[str]:

    crops = parameters["crops"]

    crop_counter = 0
    output_info = list()

    for crop in crops:
        # Blender generates file name using frame number. Avoid this and set
        # your own name without changes.
        out_filename = None
        if use_fixed_output_path:
            output_format = parameters["output_format"].lower()
            out_filename = crop["outfilebasename"] + output_format

        script_file = gen_blender_script_file(parameters,
                                              crop,
                                              mounted_paths,
                                              crop_counter,
                                              out_filename)
        cmd = gen_blender_command(parameters,
                                  crop,
                                  mounted_paths,
                                  script_file,
                                  num_threads=1,
                                  set_output_path=use_fixed_output_path)

        shell_script_file = "render-[crop_num=" + str(crop_counter) + "].sh"
        shell_script_file = os.path.join(
            scenefileeditor.get_generated_files_path(mounted_paths),
            shell_script_file)

        shell_cmd = "#!/bin/bash\n"
        for cmd_part in cmd:
            shell_cmd += " " + str(cmd_part)

        with open(shell_script_file, "w+") as sh_file:
            sh_file.write(shell_cmd)

        # Add permissions to execute script.
        st = os.stat(shell_script_file)
        os.chmod(shell_script_file, st.st_mode | stat.S_IEXEC)

        output_info.append(shell_script_file)
        crop_counter += 1

    return output_info
