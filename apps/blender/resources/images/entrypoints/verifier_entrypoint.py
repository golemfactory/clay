import json

from scripts.verifier_tools.verifier import verify

with open('params.json', 'r') as params_file:
    params = json.load(params_file)

verify(
    params['subtask_paths'],
    params['subtask_borders'],
    params['scene_path'],
    params['resolution'],
    params['samples'],
    params['frames'],
    params['output_format'],
    crops_count=params.get('crops_count', 3)
)
