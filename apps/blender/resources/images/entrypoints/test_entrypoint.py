import json
import os

from scripts.render_tools import blender_render as blender  # pylint: disable=no-name-in-module, import-error, line-too-long
from scripts.verifier_tools.verificator import verify   # pylint: disable=no-name-in-module, import-error, line-too-long


def render_whole_scene(parameters):
    # Note: params dictionary contains both: rendering parameters
    # and paths mounted by golem.
    paths = parameters

    results_info = blender.render(parameters, paths)
    print(results_info)


def sanity_check(parameters):
    verify(
        parameters['subtask_paths'],
        parameters['subtask_borders'],
        parameters['scene_path'],
        parameters['resolution'],
        parameters['samples'],
        parameters['frames'],
        parameters['output_format'],
    )


def run():
    with open('params.json', 'r') as params_file:
        params = json.load(params_file)

    render_whole_scene(params)
    outfiles = [os.path.join(params['OUTPUT_DIR'], crop['outfilebasename'])
                for crop in params['crops']]
    params['subtask_paths'] = outfiles
    sanity_check(params)


run()
