import json
from scripts.render_tools import blender_render as blender


with open('params.json', 'r') as params_file:
    params = json.load(params_file)


def run_blender_task():

    # Note: params dictionary contains both: rendering parameters
    # and paths mounted by golem.
    paths = params

    results_info = blender.render(params, paths)
    print(results_info)


run_blender_task()
