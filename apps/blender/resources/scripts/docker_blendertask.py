# pylint: disable=import-error
import params  # This module is generated before this script is run
import scripts.blender_render as blender


def run_blender_task():
    # Creates dictionary with paths to RESOURCES_DIR, WORK_DIR and OUTPUT_DIR.
    paths = blender.params_to_paths(params)

    # Creates dictionary with rendering parameters
    render_params = blender.params_to_dict(params)

    results_info = blender.render(render_params, paths)

    print(results_info)


run_blender_task()
