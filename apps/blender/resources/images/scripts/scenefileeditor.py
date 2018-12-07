import os

BLENDER_CROP_TEMPLATE_PATH \
    = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                   "templates",
                   "blendercrop.py.template")


def get_generated_files_path(mounted_paths: dict):
    return os.path.join(mounted_paths["WORK_DIR"], "render-scripts")


# pylint: disable-msg=too-many-arguments
def generate_blender_crop_file(script_file_out,
                               resolution,
                               borders_x,
                               borders_y,
                               use_compositing,
                               samples,
                               mounted_paths,
                               override_output=None):

    content = _generate_blender_crop_file(BLENDER_CROP_TEMPLATE_PATH,
                                          resolution,
                                          borders_x,
                                          borders_y,
                                          use_compositing,
                                          samples,
                                          override_output)

    scripts_dir = get_generated_files_path(mounted_paths)
    if not os.path.isdir(scripts_dir):
        os.mkdir(scripts_dir)

    blender_script_path = os.path.join(scripts_dir, script_file_out)
    with open(blender_script_path, "w+") as script_file:
        script_file.write(content)

    return blender_script_path


# pylint: disable-msg=too-many-arguments
def _generate_blender_crop_file(template_path, resolution, borders_x, borders_y,
                                use_compositing, samples, override_output=None):
    with open(template_path) as f:
        contents = f.read()

    contents %= {
        'resolution_x': resolution[0],
        'resolution_y': resolution[1],
        'border_min_x': borders_x[0],
        'border_max_x': borders_x[1],
        'border_min_y': borders_y[0],
        'border_max_y': borders_y[1],
        'use_compositing': use_compositing,
        'samples': samples,
        'override_output': override_output
    }

    return contents
