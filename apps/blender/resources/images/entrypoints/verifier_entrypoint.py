import json

from scripts.verifier_tools.verificator import verify

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
    params['basefilename'],
)
