from golem.core import common
from golem.resource import dirmanager
import os

BLENDER_CROP_TEMPLATE_PATH = dirmanager.find_task_script(
    os.path.join(common.get_golem_path(), 'apps', 'blender'), "blendercrop.py.template")
if BLENDER_CROP_TEMPLATE_PATH is None:
    raise IOError(None,
                  'Template file not found: %s' % os.path.join(common.get_golem_path(), 'apps', 'blender'))


def generate_blender_crop_file(resolution, borders_x, borders_y, use_compositing):
    with open(BLENDER_CROP_TEMPLATE_PATH) as f:
        contents = f.read()

    contents %= {
        'resolution_x': resolution[0],
        'resolution_y': resolution[1],
        'border_min_x': borders_x[0],
        'border_max_x': borders_x[1],
        'border_min_y': borders_y[0],
        'border_max_y': borders_y[1],
        'use_compositing': use_compositing,
    }

    return contents
