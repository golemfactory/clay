import json
import os
import zipfile
from pathlib import Path

from ..scripts import blender_render


def compute(
        work_dir: Path,
        network_resources_dir: Path):
    with open(work_dir / 'params.json', 'r') as f:
        params = json.load(f)
    resources_dir = work_dir / 'resources'
    resources_dir.mkdir(exist_ok=True)  # TODO remove
    result_dir = work_dir / 'result'
    result_dir.mkdir(exist_ok=True)  # TODO remove
    for rid in params['resources']:
        with zipfile.ZipFile(network_resources_dir / '{}.zip'.format(rid), 'r')\
                as zipf:
            zipf.extractall(resources_dir)

    params['scene_file'] = resources_dir / params['scene_file']
    params['crops'] = [{
        'outfilebasename': 'result',
        'borders_x': [params['borders'][0], params['borders'][2]],
        'borders_y': [params['borders'][1], params['borders'][3]],
    }]
    params.pop('borders')
    blender_render.render(
        params,
        {
            "WORK_DIR": str(work_dir),
            "OUTPUT_DIR": str(result_dir),
        },
    )

    with zipfile.ZipFile(work_dir / 'result.zip', 'w') as zipf:
        for filename in os.listdir(result_dir):
            zipf.write(result_dir / filename, filename)
            # FIXME delete raw files ?
