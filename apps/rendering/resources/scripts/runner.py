#!/usr/bin/env python3

import os
import sys

# pylint: disable=import-error
import params  # This module is generated before this script is run

if __name__ == '__main__':
    # https://stackoverflow.com/questions/16981921/relative-imports-in-python-3
    # pylint: disable:no-name-in-module
    from scripts import img_metrics_calculator
else:
    from apps.rendering.resources.scripts import img_metrics_calculator

WORK_DIR = "/golem/work"
OUTPUT_DIR = "/golem/output"


def run_img_compare_task(cropped_img_path, rendered_scene_path, xres, yres):
    """
    This script is run as an entry point for docker.
    It follows the flow of running docker in golem_core.
    It requires cropped_img and rendered_scene to be mounted to the docker.
    The 'params' also must be mounted to the docker.
    Instead of passing the arguments through stdin,
    they are written to 'params.py' file.

    :param cropped_img_path:
    :param rendered_scene_path:
    :param xres:
    :param yres:
    :return:
    """

    # print("Current dir is: %s" %
    #       os.path.dirname(os.path.realpath(__file__)))

    if not os.path.exists(cropped_img_path):
        print("Scene file '{}' does not exist".format(cropped_img_path),
              file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(rendered_scene_path):
        print("Scene file '{}' does not exist".format(rendered_scene_path),
              file=sys.stderr)
        sys.exit(1)

    dir_path = os.path.dirname(os.path.realpath(__file__))
    results_path = os.path.join(dir_path, OUTPUT_DIR[1:])
    # file_path = os.path.join(results_path, 'result.txt' )
    file_path = os.path.join(OUTPUT_DIR, 'result.txt')
    if not os.path.exists(results_path):
        os.makedirs(results_path)

    results_path = img_metrics_calculator.\
        compare_crop_window(cropped_img_path,
                            rendered_scene_path,
                            xres, yres,
                            output_filename_path=file_path)

    # print(results_path)
    with open(results_path, 'r') as f:
        results = f.read()
        print(results)


run_img_compare_task(params.cropped_img_path,
                     params.rendered_scene_path,
                     params.xres, params.yres)
