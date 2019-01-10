#!/usr/bin/env python3

import json
import os
import sys

if __name__ == '__main__':
    # https://stackoverflow.com/questions/16981921/relative-imports-in-python-3
    # pylint: disable:no-name-in-module
    from scripts import img_metrics_calculator
else:
    from golem.verificator.docker.blender.images.scripts import img_metrics_calculator


with open('params.json', 'r') as params_file:
    params = json.load(params_file)


def run_img_compare_task(verification_files, xres, yres):
    """
    This script is run as an entry point for docker.
    It follows the flow of running docker in golem_core.
    It requires cropped_img and rendered_scene to be mounted to the docker.
    The 'params' also must be mounted to the docker.
    Instead of passing the arguments through stdin,
    they are written to 'params.json' file.

    :param verification_files:
    :param xres:
    :param yres:
    :return:
    """

    # print("Current dir is: %s" %
    #       os.path.dirname(os.path.realpath(__file__)))
    counter = 0
    for rendered_scene_path, cropped_img_path in verification_files.items():
        if not os.path.exists(cropped_img_path):
            print("Scene file '{}' does not exist".format(cropped_img_path),
                file=sys.stderr)
            sys.exit(1)

        if not os.path.exists(rendered_scene_path):
            print("Scene file '{}' does not exist".format(rendered_scene_path),
                file=sys.stderr)
            sys.exit(1)

        dir_path = os.path.dirname(os.path.realpath(__file__))
        results_path = os.path.join(dir_path, params['OUTPUT_DIR'][1:])
        file_path = os.path.join(
            params['OUTPUT_DIR'], 'result_' + str(counter) + '.txt')
        if not os.path.exists(results_path):
            os.makedirs(results_path)

        results_path = img_metrics_calculator.\
            calculate_metrics(cropped_img_path,
                              rendered_scene_path,
                              xres,
                              yres,
                              metrics_output_filename=file_path)

        counter += 1

        # print(results_path)
        with open(results_path, 'r') as f:
            results = f.read()
            print(results)


run_img_compare_task(
    params['verification_files'],
    params['xres'],
    params['yres'],
)
