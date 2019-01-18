from __future__ import print_function

import cloudpickle
import functools
import json
import os
import traceback

with open('params.json', 'rb') as params_file:
    params = cloudpickle.load(params_file)

result_obj = {}

result_path = os.path.join(os.environ['OUTPUT_DIR'],
                        'result.txt')

def write_path(path, content):
    with open(path, 'w') as out:
        out.write(content)

write_result = functools.partial(write_path, result_path)

try:
    method_code = cloudpickle.loads(params['method'])
    args = cloudpickle.loads(params['args'])
    result = method_code(args)
except Exception as e:
    result_obj['error'] = str(e)
else:
    result_obj['data'] = result

write_result(json.dumps(result_obj))