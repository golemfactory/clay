from __future__ import print_function
import base64
import functools
import json
import os

import cloudpickle


def run_job():
    with open('params.json', 'r') as params_file:
        params = json.load(params_file)

    result_obj = {}

    result_path = os.path.join(os.environ['OUTPUT_DIR'],
                               'result.json')

    def write_path(path, content):
        with open(path, 'w') as out:
            out.write(content)

    write_result = functools.partial(write_path, result_path)

    try:
        method_code = cloudpickle.loads(base64.b64decode(params['method']))
        args = cloudpickle.loads(base64.b64decode(params['args']))
        result = method_code(args)
        result_obj['data'] = result
        write_result(json.dumps(result_obj))
    except Exception as e:  # pylint: disable=broad-except
        result_obj['error'] = '{}:{}'.format(e.__class__, str(e))
        write_result(json.dumps(result_obj))


if __name__ == '__main__':
    run_job()
